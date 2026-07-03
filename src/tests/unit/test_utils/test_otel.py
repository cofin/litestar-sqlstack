"""Unit tests for OTEL utilities module."""
from __future__ import annotations

from sqlstack.utils.otel import SpanStub, TracerStub, create_enqueue_span, create_job_span, end_job_span, get_tracer


class TestSpanStub:
    def test_creation(self) -> None:
        span = SpanStub()
        assert span is not None

    def test_set_attribute_no_op(self) -> None:
        span = SpanStub()
        span.set_attribute("key", "value")
        span.set_attribute("number", 123)

    def test_set_status_no_op(self) -> None:
        span = SpanStub()
        span.set_status("ok")
        span.set_status(None)

    def test_record_exception_no_op(self) -> None:
        span = SpanStub()
        span.record_exception(ValueError("test error"))

    def test_end_no_op(self) -> None:
        span = SpanStub()
        span.end()

    def test_context_manager(self) -> None:
        with SpanStub() as span:
            assert isinstance(span, SpanStub)
            span.set_attribute("test", "value")

    def test_context_manager_with_exception(self) -> None:
        try:
            with SpanStub():
                raise ValueError("test")
        except ValueError:
            pass


class TestTracerStub:
    def test_creation(self) -> None:
        t = TracerStub()
        assert t is not None

    def test_start_span_returns_stub(self) -> None:
        t = TracerStub()
        span = t.start_span("test_span")
        assert isinstance(span, SpanStub)

    def test_start_span_with_kwargs(self) -> None:
        t = TracerStub()
        span = t.start_span("test_span", context=None, kind=None)
        assert isinstance(span, SpanStub)

    def test_start_as_current_span_returns_stub(self) -> None:
        t = TracerStub()
        span = t.start_as_current_span("test_span")
        assert isinstance(span, SpanStub)


class TestGetTracer:
    def test_default_name(self) -> None:
        result = get_tracer()
        assert result is not None

    def test_custom_name(self) -> None:
        result = get_tracer("custom_service")
        assert result is not None

    def test_returns_tracer_like(self) -> None:
        result = get_tracer()
        assert hasattr(result, "start_span")


class TestCreateJobSpan:
    def test_basic_usage(self) -> None:
        t = get_tracer()
        span = create_job_span(t, "job-123", "test_function")
        assert span is not None

    def test_returns_span_like(self) -> None:
        t = get_tracer()
        span = create_job_span(t, "job-123", "test_function")
        assert hasattr(span, "set_attribute")
        assert hasattr(span, "end")


class TestEndJobSpan:
    def test_success(self) -> None:
        span = SpanStub()
        end_job_span(span, status="completed")

    def test_failure(self) -> None:
        span = SpanStub()
        end_job_span(span, status="failed", error=ValueError("oops"))

    def test_none_span(self) -> None:
        end_job_span(None, status="completed")

    def test_full_workflow(self) -> None:
        t = get_tracer()
        span = create_job_span(t, "job-456", "process_batch")
        assert span is not None
        span.set_attribute("batch_size", 50)
        end_job_span(span, status="completed")


class TestCreateEnqueueSpan:
    def test_basic_usage(self) -> None:
        t = get_tracer()
        span = create_enqueue_span(t, "my_job")
        assert span is not None
        assert hasattr(span, "set_attribute")
