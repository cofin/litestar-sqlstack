"""Unit tests for OTEL utilities module."""

from __future__ import annotations

from uuid import uuid4

from sqlstack.utils.otel import StubSpan, StubTracer, create_job_span, create_span, end_job_span, get_tracer, tracer


class TestStubSpan:
    """Tests for StubSpan class."""

    def test_stub_span_creation(self) -> None:
        """Test StubSpan can be created."""
        span = StubSpan()
        assert span is not None

    def test_set_attribute_no_op(self) -> None:
        """Test set_attribute is a no-op."""
        span = StubSpan()
        # Should not raise
        span.set_attribute("key", "value")
        span.set_attribute("number", 123)
        span.set_attribute("boolean", True)

    def test_set_status_no_op(self) -> None:
        """Test set_status is a no-op."""
        span = StubSpan()
        # Should not raise
        span.set_status("ok")
        span.set_status(None)

    def test_record_exception_no_op(self) -> None:
        """Test record_exception is a no-op."""
        span = StubSpan()
        # Should not raise
        span.record_exception(ValueError("test error"))

    def test_end_no_op(self) -> None:
        """Test end is a no-op."""
        span = StubSpan()
        # Should not raise
        span.end()

    def test_context_manager(self) -> None:
        """Test StubSpan works as context manager."""
        with StubSpan() as span:
            assert isinstance(span, StubSpan)
            span.set_attribute("test", "value")

    def test_context_manager_exit(self) -> None:
        """Test StubSpan context manager exit doesn't raise."""

        with StubSpan():
            pass  # Should not raise on exit

    def test_context_manager_with_exception(self) -> None:
        """Test StubSpan context manager handles exceptions."""
        try:
            with StubSpan():
                msg = "test"
                raise ValueError(msg)
        except ValueError:
            pass  # Expected


class TestStubTracer:
    """Tests for StubTracer class."""

    def test_stub_tracer_creation(self) -> None:
        """Test StubTracer can be created."""
        tracer = StubTracer()
        assert tracer is not None

    def test_start_span_returns_stub_span(self) -> None:
        """Test start_span returns a StubSpan."""
        tracer = StubTracer()
        span = tracer.start_span("test_span")
        assert isinstance(span, StubSpan)

    def test_start_span_with_kwargs(self) -> None:
        """Test start_span accepts arbitrary kwargs."""
        tracer = StubTracer()
        span = tracer.start_span("test_span", parent=None, context=None)
        assert isinstance(span, StubSpan)

    def test_start_as_current_span_returns_stub_span(self) -> None:
        """Test start_as_current_span returns a StubSpan."""
        tracer = StubTracer()
        span = tracer.start_as_current_span("test_span")
        assert isinstance(span, StubSpan)


class TestGetTracer:
    """Tests for get_tracer function."""

    def test_get_tracer_default_name(self) -> None:
        """Test get_tracer with default name."""
        result = get_tracer()
        assert result is not None

    def test_get_tracer_custom_name(self) -> None:
        """Test get_tracer with custom name."""
        result = get_tracer("custom_service")
        assert result is not None

    def test_get_tracer_returns_tracer(self) -> None:
        """Test get_tracer returns something usable as a tracer."""
        result = get_tracer()
        # Should have start_span method
        assert hasattr(result, "start_span")


class TestDefaultTracer:
    """Tests for default tracer instance."""

    def test_tracer_exists(self) -> None:
        """Test default tracer is created."""
        assert tracer is not None

    def test_tracer_has_start_span(self) -> None:
        """Test tracer has start_span method."""
        assert hasattr(tracer, "start_span")


class TestCreateSpan:
    """Tests for create_span context manager."""

    def test_create_span_basic(self) -> None:
        """Test create_span basic usage."""
        with create_span("test_operation") as span:
            assert span is not None

    def test_create_span_with_attributes(self) -> None:
        """Test create_span with attributes."""
        with create_span("test_operation", attributes={"key": "value", "count": 42}) as span:
            assert span is not None

    def test_create_span_returns_stub_when_otel_unavailable(self) -> None:
        """Test create_span returns StubSpan when OTEL not available."""
        # Since we're testing without OTEL installed, should get StubSpan
        with create_span("test") as span:
            # StubSpan has set_attribute method
            span.set_attribute("test", "value")

    def test_create_span_exception_handling(self) -> None:
        """Test create_span handles exceptions properly."""
        try:
            with create_span("failing_operation"):
                msg = "test error"
                raise ValueError(msg)
        except ValueError:
            pass  # Expected, span should be properly cleaned up


class TestCreateJobSpan:
    """Tests for create_job_span function."""

    def test_create_job_span_basic(self) -> None:
        """Test create_job_span basic usage."""
        task_id = uuid4()
        span = create_job_span(task_id, "test_function")
        assert span is not None

    def test_create_job_span_with_string_id(self) -> None:
        """Test create_job_span with string task ID."""
        span = create_job_span("task-123", "process_data")
        assert span is not None

    def test_create_job_span_returns_span_like_object(self) -> None:
        """Test create_job_span returns object with span methods."""
        span = create_job_span(uuid4(), "test_job")
        # Should have set_attribute method
        assert hasattr(span, "set_attribute")
        assert hasattr(span, "end")


class TestEndJobSpan:
    """Tests for end_job_span function."""

    def test_end_job_span_success(self) -> None:
        """Test end_job_span with success."""
        span = StubSpan()
        # Should not raise
        end_job_span(span, success=True)

    def test_end_job_span_failure(self) -> None:
        """Test end_job_span with failure."""
        span = StubSpan()
        # Should not raise
        end_job_span(span, success=False, error="Something went wrong")

    def test_end_job_span_with_result(self) -> None:
        """Test end_job_span with result data."""
        span = StubSpan()
        # Should not raise
        end_job_span(span, success=True, result={"processed": 100})

    def test_end_job_span_full_workflow(self) -> None:
        """Test complete job span workflow."""
        # Simulate job execution with span
        task_id = uuid4()
        span = create_job_span(task_id, "process_batch")

        # Simulate job work
        span.set_attribute("batch_size", 50)

        # End span
        end_job_span(span, success=True, result={"items_processed": 50})

    def test_end_job_span_error_workflow(self) -> None:
        """Test job span workflow with error."""
        task_id = uuid4()
        span = create_job_span(task_id, "failing_job")

        try:
            msg = "Job failed"
            raise ValueError(msg)
        except ValueError as e:
            end_job_span(span, success=False, error=str(e))


class TestIntegration:
    """Integration tests for OTEL utilities."""

    def test_full_tracing_workflow(self) -> None:
        """Test complete tracing workflow without OTEL."""
        with create_span("parent_operation", attributes={"user_id": "123"}) as parent_span:
            parent_span.set_attribute("request_id", "abc")

            with create_span("child_operation") as child_span:
                child_span.set_attribute("step", 1)

        # Should complete without errors

    def test_job_tracing_in_span_context(self) -> None:
        """Test job tracing within a span context."""
        with create_span("http_request") as request_span:
            request_span.set_attribute("path", "/api/jobs")

            # Create job span
            job_span = create_job_span(uuid4(), "async_task")
            job_span.set_attribute("queued_at", "2024-01-01T00:00:00Z")

            # End job span
            end_job_span(job_span, success=True)

        # Should complete without errors
