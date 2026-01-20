"""OpenTelemetry utilities with stub support.

This module provides OpenTelemetry instrumentation utilities that
gracefully fall back to no-ops when OpenTelemetry is not installed.

This allows code to be instrumented with tracing without requiring
OpenTelemetry as a hard dependency.

Example:
    from sqlstack.utils.otel import create_span, tracer

    with create_span("my_operation") as span:
        span.set_attribute("key", "value")
        # Do work...

For worker job tracing:
    from sqlstack.utils.otel import create_job_span, end_job_span

    span = create_job_span(task_id, function_name)
    try:
        result = await execute_job()
        end_job_span(span, success=True)
    except Exception as e:
        end_job_span(span, success=False, error=str(e))
        raise
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = [
    "OTEL_AVAILABLE",
    "create_job_span",
    "create_span",
    "end_job_span",
    "get_tracer",
    "tracer",
]

# Check if OpenTelemetry is available
try:
    from opentelemetry import trace  # pragma: nocover
    from opentelemetry.trace import Span, Tracer  # pragma: nocover

    OTEL_AVAILABLE = True  # pragma: nocover
except ImportError:
    OTEL_AVAILABLE = False
    trace = None  # type: ignore[assignment]
    Span = None  # type: ignore[assignment, misc]
    Tracer = None  # type: ignore[assignment, misc]


class StubSpan:
    """Stub span implementation when OpenTelemetry is not available."""

    def set_attribute(self, key: str, value: Any) -> None:
        """No-op attribute setter."""

    def set_status(self, status: Any) -> None:
        """No-op status setter."""

    def record_exception(self, exception: Exception) -> None:
        """No-op exception recorder."""

    def end(self) -> None:
        """No-op end."""

    def __enter__(self) -> "StubSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class StubTracer:
    """Stub tracer implementation when OpenTelemetry is not available."""

    def start_span(self, name: str, **kwargs: Any) -> StubSpan:
        """Return a stub span."""
        return StubSpan()

    def start_as_current_span(self, name: str, **kwargs: Any) -> StubSpan:
        """Return a stub span as context manager."""
        return StubSpan()


def get_tracer(name: str = "sqlstack") -> Any:
    """Get a tracer instance.

    Returns a real OpenTelemetry tracer if available, otherwise a stub.

    Args:
        name: The tracer name (typically the module/service name)

    Returns:
        A tracer instance (real or stub)
    """
    if OTEL_AVAILABLE and trace is not None:  # pragma: nocover
        return trace.get_tracer(name)
    return StubTracer()


# Default tracer instance
tracer = get_tracer()


@contextmanager
def create_span(
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """Create a tracing span.

    Args:
        name: The span name
        attributes: Optional attributes to add to the span

    Yields:
        The span instance (real or stub)
    """
    if OTEL_AVAILABLE:  # pragma: nocover
        span = tracer.start_span(name)
        try:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            yield span
        finally:
            span.end()
    else:
        yield StubSpan()


def create_job_span(task_id: Any, function_name: str) -> Any:
    """Create a span for a background job execution.

    Args:
        task_id: The task identifier
        function_name: The name of the job function

    Returns:
        The span instance (real or stub)
    """
    if OTEL_AVAILABLE:  # pragma: nocover
        span = tracer.start_span(
            f"job:{function_name}",
        )
        span.set_attribute("job.task_id", str(task_id))
        span.set_attribute("job.function", function_name)
        return span
    return StubSpan()


def end_job_span(
    span: Any,
    *,
    success: bool = True,
    error: str | None = None,
    result: dict[str, Any] | None = None,
) -> None:
    """End a job span with status.

    Args:
        span: The span to end
        success: Whether the job completed successfully
        error: Error message if failed
        result: Optional result data to record
    """
    if OTEL_AVAILABLE and trace is not None:  # pragma: nocover
        from opentelemetry.trace import StatusCode

        if success:
            span.set_status(trace.Status(StatusCode.OK))
        else:
            span.set_status(trace.Status(StatusCode.ERROR, description=error))
            if error:
                span.set_attribute("job.error", error)

        if result:
            span.set_attribute("job.result", str(result))

    span.end()
