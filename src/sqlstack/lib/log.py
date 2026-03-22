"""Logging configuration and utilities for SQLStack."""

# ruff: noqa: N802  # StructlogMiddleware named for Litestar UI display

import logging
import re
import sys
import threading
from collections.abc import Iterable, Mapping, MutableMapping
from contextvars import ContextVar
from functools import lru_cache
from inspect import isawaitable
from typing import TYPE_CHECKING, Any, Literal, cast
from uuid import UUID

import structlog
from litestar.connection import Request
from litestar.data_extractors import ConnectionDataExtractor, ResponseDataExtractor
from litestar.enums import ScopeType
from litestar.exceptions import HTTPException, WebSocketException
from litestar.status_codes import HTTP_500_INTERNAL_SERVER_ERROR
from litestar.types.asgi_types import ASGIApp, Message, Receive, Scope, Send
from litestar.utils.empty import value_or_default
from litestar.utils.scope.state import ScopeState
from sqlspec.utils.correlation import CorrelationContext
from structlog.contextvars import bind_contextvars
from structlog.types import EventDict, WrappedLogger
from structlog.typing import Processor

from sqlstack.lib.settings import get_settings
from sqlstack.utils import serialization

if TYPE_CHECKING:
    from sqlstack.domain.system.schemas import JobLogCreate, JobLogLevel
    from sqlstack.domain.system.services import TaskService

LOGGER = structlog.getLogger()

# CLI mode context - when True, log functions skip structlog output
# CLI commands use rich console for user-facing output; structlog logs are noise
_cli_mode: ContextVar[bool] = ContextVar("cli_mode", default=False)


def set_cli_mode(enabled: bool = True) -> None:
    """Set CLI mode to suppress structlog output in favor of rich console.

    Args:
        enabled: True to enable CLI mode (suppress logs), False to use structlog.
    """
    _cli_mode.set(enabled)


def is_cli_mode() -> bool:
    """Check if CLI mode is enabled.

    Returns:
        True if CLI mode is enabled, False otherwise.
    """
    return _cli_mode.get()


async def log_info(message: str, *, use_logger: bool = True, **kwargs: Any) -> None:
    """Log an info message, respecting CLI mode.

    By default, logs via structlog unless CLI mode is active. CLI commands
    should use rich console for user-facing output.

    Args:
        message: The log message.
        use_logger: If True (default), use structlog unless in CLI mode.
        **kwargs: Additional context to include in the log.
    """
    if use_logger and not is_cli_mode():
        await LOGGER.ainfo(message, **kwargs)


async def log_warning(message: str, *, use_logger: bool = True, **kwargs: Any) -> None:
    """Log a warning message, respecting CLI mode.

    Args:
        message: The log message.
        use_logger: If True (default), use structlog unless in CLI mode.
        **kwargs: Additional context to include in the log.
    """
    if use_logger and not is_cli_mode():
        await LOGGER.awarning(message, **kwargs)


async def log_error(message: str, *, use_logger: bool = True, **kwargs: Any) -> None:
    """Log an error message, respecting CLI mode.

    Args:
        message: The log message.
        use_logger: If True (default), use structlog unless in CLI mode.
        **kwargs: Additional context to include in the log.
    """
    if use_logger and not is_cli_mode():
        await LOGGER.aerror(message, **kwargs)


HTTP_RESPONSE_START: Literal["http.response.start"] = "http.response.start"
HTTP_RESPONSE_BODY: Literal["http.response.body"] = "http.response.body"
REQUEST_BODY_FIELD: Literal["body"] = "body"

_settings = get_settings()


class SuppressAsyncioTaskExceptionFilter(logging.Filter):
    """Filter to suppress 'Task exception was never retrieved' messages.

    These are logged by asyncio when a task completes with an exception
    that wasn't awaited. Since we handle these exceptions explicitly in
    our code, the duplicate log is noise.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Return False to suppress log record."""
        msg = record.getMessage()
        return "Task exception was never retrieved" not in msg


@lru_cache
def is_tty() -> bool:
    return bool(sys.stderr.isatty() or sys.stdout.isatty())


def structlog_json_serializer(value: EventDict, **_: Any) -> bytes:
    return serialization.to_json(value, as_bytes=True)


def stdlib_json_serializer(value: EventDict, **_: Any) -> str:  # pragma: no cover
    return serialization.to_json(value, as_bytes=False)


def add_google_cloud_attributes(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    """Add additional formatting to the log message so that it is parsed on Google Cloud.

    Args:
        _: Wrapped logger object.
        __: Name of the wrapped method, e.g., "info", "warning", etc.
        event_dict: Current context with current event, e.g, `{"a": 42, "event": "foo"}`.

    Returns:
        `event_dict` for further processing if it does not represent a successful health check.
    """
    event_dict["severity"] = event_dict.get("level")
    event_dict["labels"] = None
    event_dict["resource"] = None
    if event_dict.get("logger"):
        event_dict["python_logger"] = event_dict.pop("logger")
    return event_dict


def add_correlation_id(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    """Add correlation_id from SQLSpec correlation context if present."""
    if "correlation_id" not in event_dict:
        event_dict.update(CorrelationContext.to_dict())
    return event_dict


class EventFilter:
    """Remove keys from the log event."""

    def __init__(self, filter_keys: Iterable[str]) -> None:
        """Event filter.

        Args:
        filter_keys: Iterable of string keys to be excluded from the log event.
        """
        self.filter_keys = filter_keys

    def __call__(self, _: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
        """Receive the log event, and filter keys."""
        for key in self.filter_keys:
            event_dict.pop(key, None)
        return event_dict


def StructlogMiddleware(app: ASGIApp) -> ASGIApp:
    """Middleware to ensure that every request has a clean structlog context.

    Args:
        app: The previous ASGI app in the call chain.

    Returns:
        A new ASGI app that cleans the structlog contextvars.
    """

    async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
        """Clean up structlog contextvars.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive handler.
            send: ASGI send handler.
        """
        structlog.contextvars.clear_contextvars()
        await app(scope, receive, send)

    return middleware


def after_exception_hook_handler(exc: Exception, _scope: Scope) -> None:
    """Binds `exc_info` key with exception instance as value to structlog
    context vars.

    This must be a coroutine so that it is not wrapped in a thread where we'll lose context.

    Args:
        exc: the exception that was raised.
        _scope: scope of the request
    """
    if isinstance(exc, HTTPException) and exc.status_code < HTTP_500_INTERNAL_SERVER_ERROR:
        return
    if isinstance(exc, WebSocketException):
        return
    bind_contextvars(exc_info=sys.exc_info())


class BeforeSendHandler:
    """Extraction of request and response data from connection scope."""

    __slots__ = (
        "do_log_request",
        "do_log_response",
        "exclude_paths",
        "include_compressed_body",
        "logger",
        "request_extractor",
        "response_extractor",
    )

    def __init__(self) -> None:
        """Configure the handler."""
        self.exclude_paths = re.compile(_settings.log.EXCLUDE_PATHS)
        self.do_log_request = bool(_settings.log.REQUEST_FIELDS)
        self.do_log_response = bool(_settings.log.RESPONSE_FIELDS)
        self.include_compressed_body = _settings.log.INCLUDE_COMPRESSED_BODY
        self.request_extractor = ConnectionDataExtractor(
            extract_body="body" in _settings.log.REQUEST_FIELDS,
            extract_client="client" in _settings.log.REQUEST_FIELDS,
            extract_content_type="content_type" in _settings.log.REQUEST_FIELDS,
            extract_cookies="cookies" in _settings.log.REQUEST_FIELDS,
            extract_headers="headers" in _settings.log.REQUEST_FIELDS,
            extract_method="method" in _settings.log.REQUEST_FIELDS,
            extract_path="path" in _settings.log.REQUEST_FIELDS,
            extract_path_params="path_params" in _settings.log.REQUEST_FIELDS,
            extract_query="query" in _settings.log.REQUEST_FIELDS,
            extract_scheme="scheme" in _settings.log.REQUEST_FIELDS,
            obfuscate_cookies=_settings.log.OBFUSCATE_COOKIES,
            obfuscate_headers=_settings.log.OBFUSCATE_HEADERS,
            parse_body=False,
            parse_query=False,
        )
        self.response_extractor = ResponseDataExtractor(
            extract_body="body" in _settings.log.RESPONSE_FIELDS,
            extract_headers="headers" in _settings.log.RESPONSE_FIELDS,
            extract_status_code="status_code" in _settings.log.RESPONSE_FIELDS,
            obfuscate_cookies=_settings.log.OBFUSCATE_COOKIES,
            obfuscate_headers=_settings.log.OBFUSCATE_HEADERS,
        )

    async def __call__(self, message: Message, scope: Scope) -> None:
        """Receives ASGI response messages and scope, and logs per
        configuration.

        Args:
            message: ASGI response event.
            scope: ASGI connection scope.
        """
        if scope["type"] != ScopeType.HTTP:
            return
        if self.exclude_paths.findall(scope["path"]):
            return

        if message["type"] == HTTP_RESPONSE_START:
            scope["state"]["log_level"] = (
                logging.ERROR if message["status"] >= HTTP_500_INTERNAL_SERVER_ERROR else logging.INFO
            )
            scope["state"][HTTP_RESPONSE_START] = message

        elif message["type"] == HTTP_RESPONSE_BODY and message["more_body"] is False:
            scope["state"][HTTP_RESPONSE_BODY] = message
            try:
                if self.do_log_request:
                    await self.log_request(scope)
                if self.do_log_response:
                    await self.log_response(scope)
                await LOGGER.alog(
                    scope["state"]["log_level"],
                    f"{scope['method'] if scope['type'] == ScopeType.HTTP else scope['type']} {scope['path']}",
                )

            except Exception as e:  # noqa: BLE001  # pylint: disable=broad-except
                structlog.contextvars.clear_contextvars()
                await LOGGER.aerror("Error in logging before-send handler!", reason=f"{type(e).__name__}{e.args}")

    async def log_request(self, scope: Scope) -> None:
        """Handle extracting the request data and logging the message.

        Args:
            scope: The ASGI connection scope.
        """
        extracted_data = await self.extract_request_data(request=scope["app"].request_class(scope))  # pyright: ignore
        structlog.contextvars.bind_contextvars(**extracted_data)

    async def log_response(self, scope: Scope) -> None:
        """Handle extracting the response data and logging the message.

        Args:
            scope: The ASGI connection scope.
        """
        extracted_data = self.extract_response_data(scope=scope)
        structlog.contextvars.bind_contextvars(**extracted_data)

    async def extract_request_data(self, request: Request[Any, Any, Any]) -> dict[str, Any]:
        """Create a dictionary of values for the log.

        Args:
            request: A request instance.

        Raises:
            RuntimeError:

        Returns:
            An OrderedDict.
        """
        data: dict[str, Any] = {}
        extracted_data = self.request_extractor(connection=request)
        missing = object()
        for key in _settings.log.REQUEST_FIELDS:
            value = extracted_data.get(key, missing)
            if value is missing:  # pragma: no cover
                continue
            if isawaitable(value):
                try:
                    value = await value
                except RuntimeError:
                    if key != REQUEST_BODY_FIELD:
                        raise  # pragma: no cover
                    value = None
            data[key] = value
        return data

    def extract_response_data(self, scope: Scope) -> dict[str, Any]:
        """Extract data from the response.

        Args:
            scope: The ASGI connection scope.

        Returns:
            An OrderedDict.
        """
        data: dict[str, Any] = {}
        extracted_data = self.response_extractor(
            messages=(scope["state"][HTTP_RESPONSE_START], scope["state"][HTTP_RESPONSE_BODY])
        )
        missing = object()
        connection_state = ScopeState.from_scope(scope)
        response_body_compressed = value_or_default(connection_state.response_compressed, False)
        for key in _settings.log.RESPONSE_FIELDS:
            value = extracted_data.get(key, missing)
            if key == "body" and response_body_compressed and not self.include_compressed_body:
                continue
            if value is missing:  # pragma: no cover
                continue
            data[key] = value
        return data


def structlog_processors(as_json: bool) -> list[Processor]:
    """Set the default processors for structlog.

    Returns:
        An optional list of processors.
    """
    try:
        import structlog
        from structlog.dev import RichTracebackFormatter

        # The capture processor uses the module-level buffer reference.
        # It is a no-op in web/CLI processes (buffer is None) and activates
        # when the worker calls set_buffer() at startup.
        capture_processor = JobLogCaptureProcessor(None)

        if as_json:
            return [
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                capture_processor,
                add_correlation_id,
                structlog.processors.format_exc_info,
                add_google_cloud_attributes,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(serializer=structlog_json_serializer),
            ]
        return [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            capture_processor,
            add_correlation_id,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(
                colors=True, exception_formatter=RichTracebackFormatter(max_frames=1, show_locals=False, width=80)
            ),
        ]
    except ImportError:
        return []


def stdlib_logger_processors(as_json: bool) -> list[Processor]:
    """Set the default processors for structlog stdlib.

    Returns:
        An optional list of processors.
    """
    try:
        import structlog
        from structlog.dev import RichTracebackFormatter

        if as_json:
            return [
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.add_log_level,
                structlog.stdlib.ExtraAdder(),
                add_correlation_id,
                EventFilter(["color_message"]),
                structlog.processors.EventRenamer("message"),
                add_google_cloud_attributes,
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(serializer=stdlib_json_serializer),
            ]
        return [
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.stdlib.ExtraAdder(),
            add_correlation_id,
            EventFilter(["color_message"]),
            EventFilter(["message"]),
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(
                colors=True, exception_formatter=RichTracebackFormatter(max_frames=1, show_locals=False, width=80)
            ),
        ]
    except ImportError:
        return []


# ── Job Log Capture ───────────────────────────────────────────────

# Keys excluded from the ``detail`` JSONB payload.
_EXCLUDED_DETAIL_KEYS = frozenset({
    "job_id",
    "job_function",
    "team_id",
    "level",
    "event",
    "timestamp",
    "_record",
    "_from_decorator",
})

# Ordered (pattern, stage) pairs for heuristic detection.
_STAGE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"cleanup|cleaning up", re.IGNORECASE), "cleanup"),
    (re.compile(r"executing job", re.IGNORECASE), "job_start"),
    (re.compile(r"job completed|task completed", re.IGNORECASE), "job_complete"),
    (re.compile(r"job failed|job timed out|processing failed", re.IGNORECASE), "job_error"),
]


def detect_stage(event_dict: Mapping[str, Any]) -> str:
    """Determine the pipeline stage from event dict contents."""
    if "stage" in event_dict:
        return str(event_dict["stage"])

    event_text = str(event_dict.get("event", ""))
    for pattern, stage in _STAGE_PATTERNS:
        if pattern.search(event_text):
            return stage
    return "processing"


class JobLogBuffer:
    """Thread-safe buffer that accumulates log entries and flushes to PostgreSQL."""

    def __init__(self, *, flush_interval: float = 1.0, flush_size: int = 20) -> None:
        self._entries: list["JobLogCreate"] = []
        self._sequence_counters: dict[str, int] = {}
        self._lock = threading.Lock()
        self.flush_interval = flush_interval
        self.flush_size = flush_size

    def append(
        self,
        *,
        job_id: str,
        level: str,
        message: str,
        stage: str,
        detail: dict[str, Any],
        team_id: str | None = None,
    ) -> None:
        """Append a log entry (called from sync structlog processor context)."""
        from sqlstack.domain.system.schemas import JobLogCreate

        with self._lock:
            seq = self._sequence_counters.get(job_id, 0)
            self._sequence_counters[job_id] = seq + 1
            self._entries.append(
                JobLogCreate(
                    job_id=UUID(job_id),
                    stage=stage,
                    level=cast("JobLogLevel", level),
                    message=message,
                    detail=detail,
                    sequence=seq,
                    team_id=UUID(team_id) if team_id else None,
                )
            )

    async def flush(self, task_service: "TaskService") -> int:
        """Flush buffered entries to the database."""
        with self._lock:
            if not self._entries:
                return 0
            batch = list(self._entries)
            self._entries.clear()
        try:
            count = await task_service.create_job_logs(batch)
        except Exception as flush_exc:  # noqa: BLE001
            await LOGGER.awarning(
                "Failed to flush job log buffer — entries preserved for retry",
                entry_count=len(batch),
                error=f"{type(flush_exc).__name__}: {flush_exc}",
                exc_info=flush_exc,
            )
            with self._lock:
                self._entries = batch + self._entries
            return 0
        return count

    def reset_sequences(self, job_id: str) -> None:
        """Remove sequence counter and any unflushed entries for a completed/failed job."""
        job_uuid = UUID(job_id)
        with self._lock:
            self._sequence_counters.pop(job_id, None)
            self._entries = [e for e in self._entries if e.job_id != job_uuid]

    @property
    def pending_count(self) -> int:
        """Number of buffered entries awaiting flush."""
        with self._lock:
            return len(self._entries)


class JobLogCaptureProcessor:
    """Structlog processor that captures events for persistence when ``job_id`` is in context."""

    def __init__(self, buffer: "JobLogBuffer | None") -> None:
        self.buffer = buffer

    def __call__(
        self, _logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
    ) -> MutableMapping[str, Any]:
        buffer = self.buffer if self.buffer is not None else _active_buffer
        if buffer is None:
            return event_dict

        job_id = event_dict.get("job_id")
        if job_id is None:
            return event_dict

        level_raw = event_dict.get("level", method_name or "info")
        level = str(level_raw).upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            level = "INFO"

        team_id = event_dict.get("team_id")
        buffer.append(
            job_id=str(job_id),
            level=level,
            message=str(event_dict.get("event", "")),
            stage=detect_stage(event_dict),
            detail={k: v for k, v in event_dict.items() if k not in _EXCLUDED_DETAIL_KEYS},
            team_id=str(team_id) if team_id else None,
        )
        return event_dict


# Module-level buffer reference.  ``None`` outside worker processes.
_active_buffer: JobLogBuffer | None = None


def get_buffer() -> JobLogBuffer | None:
    """Return the active buffer (``None`` outside worker processes)."""
    return _active_buffer


def set_buffer(buffer: JobLogBuffer | None) -> None:
    """Set the module-level active buffer."""
    global _active_buffer  # noqa: PLW0603
    _active_buffer = buffer
