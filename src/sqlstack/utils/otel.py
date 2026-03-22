# ruff: noqa: RUF100, PLR0913, A002, ARG001, ARG002, B903, PLR0917
# mypy: disable-error-code="misc,assignment,import-not-found,unused-ignore,valid-type,no-any-return,attr-defined,unreachable"
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportMissingImports=false, reportInvalidTypeForm=false
"""OpenTelemetry support with optional dependency and instrumentation utilities.

This module provides:
1. Stub implementations of OpenTelemetry types when the package isn't installed
2. Real types when opentelemetry is available
3. Instrumentation utilities for SQLStack worker jobs

Pattern inspired by litestar-saq and sqlspec.
"""

from collections.abc import Mapping
from importlib.util import find_spec
from typing import Any, Self

__all__ = (
    "OPENTELEMETRY_INSTALLED",
    "Context",
    "Span",
    "SpanKind",
    "Status",
    "StatusCode",
    "Tracer",
    "create_enqueue_span",
    "create_job_span",
    "end_job_span",
    "extract_trace_context",
    "get_tracer",
    "inject_trace_context",
    "propagate",
    "trace",
)


# =============================================================================
# Stub Implementations (used when OpenTelemetry is not installed)
# =============================================================================


class SpanStub:
    """Placeholder implementation for opentelemetry.trace.Span."""

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute (no-op when OTEL not installed)."""

    def set_attributes(self, attributes: Mapping[str, Any]) -> None:
        """Set multiple span attributes (no-op when OTEL not installed)."""

    def add_event(self, name: str, attributes: Mapping[str, Any] | None = None, timestamp: int | None = None) -> None:
        """Add an event to the span (no-op when OTEL not installed)."""

    def record_exception(
        self,
        exception: BaseException,
        attributes: Mapping[str, Any] | None = None,
        timestamp: int | None = None,
        escaped: bool = False,
    ) -> None:
        """Record an exception (no-op when OTEL not installed)."""

    def set_status(self, status: Any, description: str | None = None) -> None:
        """Set span status (no-op when OTEL not installed)."""

    def end(self, end_time: int | None = None) -> None:
        """End the span (no-op when OTEL not installed)."""

    def get_span_context(self) -> Any:
        """Get span context (returns None when OTEL not installed)."""
        return None

    def is_recording(self) -> bool:
        """Check if span is recording (returns False when OTEL not installed)."""
        return False

    def __enter__(self) -> Self:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Context manager exit."""


class TracerStub:
    """Placeholder implementation for opentelemetry.trace.Tracer."""

    def start_span(
        self,
        name: str,
        context: Any = None,
        kind: Any = None,
        attributes: Any = None,
        links: Any = None,
        start_time: Any = None,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
    ) -> SpanStub:
        """Start a new span (returns stub when OTEL not installed)."""
        return SpanStub()

    def start_as_current_span(
        self,
        name: str,
        context: Any = None,
        kind: Any = None,
        attributes: Any = None,
        links: Any = None,
        start_time: Any = None,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
        end_on_exit: bool = True,
    ) -> SpanStub:
        """Start span as current (returns stub when OTEL not installed)."""
        return SpanStub()


class SpanKindStub:
    """Placeholder for opentelemetry.trace.SpanKind enum."""

    INTERNAL = 0
    SERVER = 1
    CLIENT = 2
    PRODUCER = 3
    CONSUMER = 4


class StatusCodeStub:
    """Placeholder for opentelemetry.trace.StatusCode enum."""

    UNSET = 0
    OK = 1
    ERROR = 2


class StatusStub:
    """Placeholder for opentelemetry.trace.Status."""

    def __init__(self, status_code: Any = None, description: str | None = None) -> None:
        self.status_code = status_code
        self.description = description


class _TraceModuleStub:
    """Placeholder for opentelemetry.trace module."""

    def get_tracer(
        self,
        instrumenting_module_name: str,
        instrumenting_library_version: str | None = None,
        schema_url: str | None = None,
        tracer_provider: Any = None,
    ) -> TracerStub:
        """Get a tracer instance (returns stub when OTEL not installed)."""
        return TracerStub()

    def get_current_span(self, context: Any = None) -> SpanStub:
        """Get current span (returns stub when OTEL not installed)."""
        return SpanStub()

    def set_span_in_context(self, span: Any, context: Any = None) -> Any:
        """Set span in context (no-op when OTEL not installed)."""
        return context


class _PropagateModuleStub:
    """Placeholder for opentelemetry.propagate module."""

    def inject(self, carrier: dict[str, str], context: Any = None, setter: Any = None) -> None:
        """Inject trace context into carrier (no-op when OTEL not installed)."""

    def extract(self, carrier: dict[str, str], context: Any = None, getter: Any = None) -> Any:
        """Extract trace context from carrier (returns None when OTEL not installed)."""
        return None


class _ContextStub:
    """Placeholder for opentelemetry.context.Context."""


# =============================================================================
# Type Detection and Assignment
# =============================================================================

OPENTELEMETRY_INSTALLED: bool = find_spec("opentelemetry") is not None

if OPENTELEMETRY_INSTALLED:
    from opentelemetry import propagate as _real_propagate  # pyright: ignore[reportMissingImports]
    from opentelemetry import trace as _real_trace  # pyright: ignore[reportMissingImports]
    from opentelemetry.context import Context as _RealContext  # pyright: ignore[reportMissingImports]
    from opentelemetry.trace import Span as _RealSpan  # pyright: ignore[reportMissingImports]
    from opentelemetry.trace import SpanKind as _RealSpanKind  # pyright: ignore[reportMissingImports]
    from opentelemetry.trace import Status as _RealStatus  # pyright: ignore[reportMissingImports]
    from opentelemetry.trace import StatusCode as _RealStatusCode  # pyright: ignore[reportMissingImports]
    from opentelemetry.trace import Tracer as _RealTracer  # pyright: ignore[reportMissingImports]

    Span = _RealSpan  # pyright: ignore[reportConstantRedefinition]
    SpanKind = _RealSpanKind  # pyright: ignore[reportConstantRedefinition]
    Status = _RealStatus  # pyright: ignore[reportConstantRedefinition]
    StatusCode = _RealStatusCode  # pyright: ignore[reportConstantRedefinition]
    Tracer = _RealTracer  # pyright: ignore[reportConstantRedefinition]
    Context = _RealContext  # pyright: ignore[reportConstantRedefinition]
    trace = _real_trace  # pyright: ignore[reportConstantRedefinition]
    propagate = _real_propagate  # pyright: ignore[reportConstantRedefinition]
else:
    Span = SpanStub  # type: ignore[misc,assignment]
    SpanKind = SpanKindStub  # type: ignore[misc,assignment]
    Status = StatusStub  # type: ignore[misc,assignment]
    StatusCode = StatusCodeStub  # type: ignore[misc,assignment]
    Tracer = TracerStub  # type: ignore[misc,assignment]
    Context = _ContextStub  # type: ignore[misc,assignment]
    trace = _TraceModuleStub()  # type: ignore[assignment]
    propagate = _PropagateModuleStub()  # type: ignore[assignment]


# =============================================================================
# Instrumentation Utilities
# =============================================================================

_tracer: Tracer | None = None


def get_tracer(name: str = "sqlstack.worker", version: str | None = None) -> Tracer:
    """Get or create the tracer instance.

    Args:
        name: Instrumenting module name.
        version: Instrumenting module version.

    Returns:
        Tracer instance (real or stub depending on OPENTELEMETRY_INSTALLED).
    """
    global _tracer  # noqa: PLW0603
    if _tracer is None:
        _tracer = trace.get_tracer(name, version)
    return _tracer


def inject_trace_context(data: dict[str, Any]) -> None:
    """Inject current trace context into job data.

    This enables distributed tracing across process boundaries by
    storing the W3C trace context in data["_otel_context"].

    Args:
        data: Job data dictionary to inject context into.
    """
    if not OPENTELEMETRY_INSTALLED:
        return

    carrier: dict[str, str] = {}
    propagate.inject(carrier)

    if carrier:
        data["_otel_context"] = carrier


def extract_trace_context(data: dict[str, Any] | None) -> Any:
    """Extract trace context from job data.

    Retrieves the stored W3C trace context from data["_otel_context"]
    and returns an OpenTelemetry Context that can be used as a parent.

    Args:
        data: Job data dictionary to extract context from.

    Returns:
        OpenTelemetry Context or None if no context found.
    """
    if not OPENTELEMETRY_INSTALLED:
        return None

    if data is None:
        return None

    carrier = data.get("_otel_context", {})
    if not carrier:
        return None

    return propagate.extract(carrier)


def create_job_span(
    tracer: Tracer, job_id: str, function_name: str, data: dict[str, Any] | None = None, *, queue_name: str = "sqlstack.jobs"
) -> Span | None:
    """Create a span for job processing (CONSUMER).

    Following OTEL messaging semantic conventions:
    - Span name: "{queue_name} process"
    - SpanKind: CONSUMER
    - Attributes follow messaging.* conventions

    Args:
        tracer: Tracer instance to use.
        job_id: Unique identifier for the job.
        function_name: Name of the job function being executed.
        data: Optional job data (used to extract parent trace context).
        queue_name: Name of the queue being processed.

    Returns:
        Created span or None if tracing unavailable.
    """
    parent_context = extract_trace_context(data)
    attributes: dict[str, Any] = {
        "messaging.system": "sqlstack",
        "messaging.operation.name": "process",
        "messaging.destination.name": queue_name,
        "messaging.message.id": job_id,
        "sqlstack.job.function": function_name,
    }

    span_kind = SpanKind.CONSUMER if OPENTELEMETRY_INSTALLED else None
    return tracer.start_span(
        name=f"{queue_name} process", context=parent_context, kind=span_kind, attributes=attributes
    )


def end_job_span(span: Span | None, *, status: str | None = None, error: BaseException | None = None) -> None:
    """End a job processing span with status and error information.

    Should be called in a finally block to ensure span is always ended.

    Args:
        span: Span to end (may be None).
        status: Optional job status string.
        error: Optional exception that occurred during processing.
    """
    if span is None:
        return

    try:
        if status is not None:
            span.set_attribute("sqlstack.job.status", status)

        if error is not None:
            if OPENTELEMETRY_INSTALLED:
                span.record_exception(error)
                span.set_status(Status(StatusCode.ERROR, str(error)))
            else:
                span.set_status(None, str(error))
        elif OPENTELEMETRY_INSTALLED:
            span.set_status(Status(StatusCode.OK))
    finally:
        span.end()


def create_enqueue_span(tracer: Tracer, function_name: str, *, queue_name: str = "sqlstack.jobs") -> Span:
    """Create a span for job enqueue (PRODUCER).

    Following OTEL messaging semantic conventions:
    - Span name: "{queue_name} publish"
    - SpanKind: PRODUCER
    - Attributes follow messaging.* conventions

    Args:
        tracer: Tracer instance to use.
        function_name: Name of the job function being enqueued.
        queue_name: Name of the queue.

    Returns:
        Created span (real or stub).
    """
    attributes: dict[str, Any] = {
        "messaging.system": "sqlstack",
        "messaging.operation.name": "publish",
        "messaging.destination.name": queue_name,
        "sqlstack.job.function": function_name,
    }

    span_kind = SpanKind.PRODUCER if OPENTELEMETRY_INSTALLED else None
    return tracer.start_as_current_span(name=f"{queue_name} publish", kind=span_kind, attributes=attributes)
