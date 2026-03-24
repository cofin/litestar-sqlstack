"""Unit tests for background worker."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from sqlstack.utils.worker import Worker


def _make_mock_container(mock_task_service: AsyncMock, mock_publisher: AsyncMock | None = None) -> MagicMock:
    """Create a mock Dishka AsyncContainer that resolves TaskService and RealtimePublisher.

    The returned mock supports ``async with container(scope=...) as req:`` and
    ``await req.get(ServiceType)`` patterns used by the Worker.
    """
    if mock_publisher is None:
        mock_publisher = AsyncMock()

    async def _get(service_type: type) -> Any:
        from sqlstack.domain.system.services import TaskService
        from sqlstack.lib.realtime import RealtimePublisher

        if service_type is TaskService:
            return mock_task_service
        if service_type is RealtimePublisher:
            return mock_publisher
        msg = f"Unexpected service type: {service_type}"
        raise ValueError(msg)

    mock_request_container = AsyncMock()
    mock_request_container.get = AsyncMock(side_effect=_get)

    @contextlib.asynccontextmanager
    async def _scope(**kwargs: Any):  # noqa: ANN003, ARG001
        yield mock_request_container

    container = MagicMock()
    container.side_effect = _scope  # container(scope=...) returns async CM
    container.close = AsyncMock()
    return container


class TestWorkerInitialization:
    """Test Worker initialization."""

    def test_worker_init_defaults(self) -> None:
        """Test worker initialization with defaults."""
        worker = Worker(register_signals=False)

        assert worker.poll_interval == 30.0  # 30-second fallback polling
        assert worker.batch_size == 10
        assert worker.shutdown_timeout == 30.0
        assert worker.running_tasks == {}

    def test_worker_init_custom_params(self) -> None:
        """Test worker initialization with custom parameters."""
        worker = Worker(poll_interval=5.0, batch_size=20, shutdown_timeout=60.0, register_signals=False)

        assert worker.poll_interval == 5.0
        assert worker.batch_size == 20
        assert worker.shutdown_timeout == 60.0

    def test_worker_shutdown_event_initialized(self) -> None:
        """Test that shutdown event is initialized."""
        worker = Worker(register_signals=False)

        assert isinstance(worker.shutdown_event, asyncio.Event)
        assert not worker.shutdown_event.is_set()

    def test_worker_job_registry_loaded(self) -> None:
        """Test that job registry is loaded on initialization."""
        from sqlstack.lib.jobs import register_job

        # Register a test job
        @register_job()
        async def test_registry_job() -> dict:
            return {"status": "ok"}

        worker = Worker(register_signals=False)

        assert isinstance(worker.job_registry, dict)
        # Should have at least the test job we just registered
        assert "test_registry_job" in worker.job_registry


class TestWorkerShutdown:
    """Test Worker shutdown handling."""

    def test_handle_shutdown_sets_event(self) -> None:
        """Test that _handle_shutdown sets shutdown event."""
        worker = Worker(register_signals=False)

        assert not worker.shutdown_event.is_set()

        worker._handle_shutdown()

        assert worker.shutdown_event.is_set()

    @pytest.mark.anyio
    async def test_cleanup_completed_tasks_removes_done_tasks(self) -> None:
        """Test that completed tasks are removed from tracking."""
        worker = Worker(register_signals=False)

        # Create real asyncio tasks
        async def quick_task() -> None:
            pass

        async def slow_task() -> None:
            await asyncio.sleep(10)

        done_task1 = asyncio.create_task(quick_task())
        done_task2 = asyncio.create_task(quick_task())
        running_task = asyncio.create_task(slow_task())

        # Wait for quick tasks to complete
        await asyncio.sleep(0.01)

        worker.running_tasks = {"task-1": done_task1, "task-2": running_task, "task-3": done_task2}

        worker._cleanup_completed_tasks()

        # Only running task should remain
        assert len(worker.running_tasks) == 1
        assert "task-2" in worker.running_tasks

        # Cleanup
        running_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await running_task


class TestWorkerTaskExecution:
    """Test Worker task execution logic."""

    @pytest.mark.anyio
    async def test_execute_task_success(self) -> None:
        """Test successful task execution."""
        worker = Worker(register_signals=False)

        # Mock task service and publisher
        mock_task_service = AsyncMock()
        mock_container = _make_mock_container(mock_task_service)

        # Register a test job
        from sqlstack.lib.jobs import _job_registry

        test_result = {"status": "success", "value": 42}

        async def test_job(param1: str, param2: int) -> dict:
            return test_result

        _job_registry["test_job"] = test_job

        # Create mock task data
        task_data = MagicMock()
        task_data.id = uuid4()
        task_data.function = "test_job"
        task_data.data = {"param1": "test", "param2": 123}

        # Replace the container with our mock
        worker.container = mock_container
        worker._heartbeat_manager = MagicMock()
        worker._heartbeat_manager.register_job = MagicMock()
        worker._heartbeat_manager.unregister_job = MagicMock()

        await worker._execute_task(task_data)

        # Should mark as completed
        mock_task_service.complete_task.assert_called_once()
        call_args = mock_task_service.complete_task.call_args
        assert call_args[0][0] == task_data.id
        assert call_args[1]["result"]["result"] == test_result

    @pytest.mark.anyio
    async def test_execute_task_unknown_function(self) -> None:
        """Test task execution with unknown function."""
        worker = Worker(register_signals=False)

        # Mock task service
        mock_task_service = AsyncMock()
        mock_container = _make_mock_container(mock_task_service)

        # Create mock task data with unknown function
        task_data = MagicMock()
        task_data.id = uuid4()
        task_data.function = "nonexistent_function"
        task_data.data = {}

        # Replace the container with our mock
        worker.container = mock_container
        worker._heartbeat_manager = MagicMock()
        worker._heartbeat_manager.register_job = MagicMock()
        worker._heartbeat_manager.unregister_job = MagicMock()

        await worker._execute_task(task_data)

        # Should mark as failed
        mock_task_service.fail_task.assert_called_once()
        call_args = mock_task_service.fail_task.call_args
        assert call_args[0][0] == task_data.id
        # Check keyword argument instead of positional
        assert "error" in call_args[1]
        assert "unknown function" in call_args[1]["error"].lower()

    @pytest.mark.anyio
    async def test_execute_task_execution_error(self) -> None:
        """Test task execution when function raises error."""
        worker = Worker(register_signals=False)

        # Mock task service
        mock_task_service = AsyncMock()
        mock_container = _make_mock_container(mock_task_service)

        # Register a job that raises an error
        from sqlstack.lib.jobs import _job_registry

        async def failing_job() -> dict:
            msg = "Test error"
            raise ValueError(msg)

        _job_registry["failing_job"] = failing_job

        # Create mock task data
        task_data = MagicMock()
        task_data.id = uuid4()
        task_data.function = "failing_job"
        task_data.data = {}

        # Replace the container with our mock
        worker.container = mock_container
        worker._heartbeat_manager = MagicMock()
        worker._heartbeat_manager.register_job = MagicMock()
        worker._heartbeat_manager.unregister_job = MagicMock()

        await worker._execute_task(task_data)

        # Should mark as failed with retry
        mock_task_service.fail_task.assert_called_once()
        call_args = mock_task_service.fail_task.call_args
        assert call_args[0][0] == task_data.id
        # Check keyword arguments
        assert "error" in call_args[1]
        assert "Test error" in call_args[1]["error"]
        assert call_args[1]["retry"] is True

    @pytest.mark.anyio
    async def test_execute_task_with_no_result(self) -> None:
        """Test task execution when function returns None."""
        worker = Worker(register_signals=False)

        # Mock task service
        mock_task_service = AsyncMock()
        mock_container = _make_mock_container(mock_task_service)

        # Register a job that returns None
        from sqlstack.lib.jobs import _job_registry

        async def no_result_job() -> None:
            pass

        _job_registry["no_result_job"] = no_result_job

        # Create mock task data
        task_data = MagicMock()
        task_data.id = uuid4()
        task_data.function = "no_result_job"
        task_data.data = {}

        # Replace the container with our mock
        worker.container = mock_container
        worker._heartbeat_manager = MagicMock()
        worker._heartbeat_manager.register_job = MagicMock()
        worker._heartbeat_manager.unregister_job = MagicMock()

        await worker._execute_task(task_data)

        # Should mark as completed with no result
        mock_task_service.complete_task.assert_called_once()
        call_args = mock_task_service.complete_task.call_args
        assert call_args[1]["result"] is None

    @pytest.mark.anyio
    async def test_execute_task_removes_from_running(self) -> None:
        """Test that task is removed from running_tasks after execution."""
        worker = Worker(register_signals=False)

        # Mock task service
        mock_task_service = AsyncMock()
        mock_container = _make_mock_container(mock_task_service)

        # Register a simple job
        from sqlstack.lib.jobs import _job_registry

        async def simple_job() -> dict:
            return {"status": "ok"}

        _job_registry["simple_job"] = simple_job

        # Create mock task data
        task_data = MagicMock()
        task_id = uuid4()
        task_data.id = task_id
        task_data.function = "simple_job"
        task_data.data = {}

        # Add to running tasks
        worker.running_tasks[str(task_id)] = AsyncMock()

        # Replace the container with our mock
        worker.container = mock_container
        worker._heartbeat_manager = MagicMock()
        worker._heartbeat_manager.register_job = MagicMock()
        worker._heartbeat_manager.unregister_job = MagicMock()

        await worker._execute_task(task_data)

        # Should be removed from running tasks
        assert str(task_id) not in worker.running_tasks


class TestWorkerProcessPendingTasks:
    """Test Worker task processing logic."""

    @pytest.mark.anyio
    async def test_process_pending_tasks_empty_queue(self) -> None:
        """Test processing when no tasks are pending."""
        worker = Worker(register_signals=False)

        # Mock task service with no pending tasks
        mock_task_service = AsyncMock()
        mock_task_service.get_pending_tasks.return_value = []
        mock_container = _make_mock_container(mock_task_service)

        worker.container = mock_container

        await worker._process_pending_tasks()

        mock_task_service.get_pending_tasks.assert_called_once_with(limit=worker.batch_size)

    @pytest.mark.anyio
    async def test_process_pending_tasks_claims_and_executes(self) -> None:
        """Test that pending tasks are claimed and executed."""
        worker = Worker(register_signals=False)

        # Mock task service
        mock_task_service = AsyncMock()
        mock_task_service.claim_task.return_value = True
        mock_container = _make_mock_container(mock_task_service)

        # Create mock pending task
        task_data = MagicMock()
        task_data.id = uuid4()
        task_data.function = "test_job"
        task_data.data = {}

        mock_task_service.get_pending_tasks.return_value = [task_data]

        # Register a job
        from sqlstack.lib.jobs import _job_registry

        async def test_job() -> dict:
            await asyncio.sleep(0.01)  # Small delay
            return {"status": "ok"}

        _job_registry["test_job"] = test_job

        worker.container = mock_container
        worker._heartbeat_manager = MagicMock()
        worker._heartbeat_manager.register_job = MagicMock()
        worker._heartbeat_manager.unregister_job = MagicMock()

        await worker._process_pending_tasks()

        # Should have claimed the task
        mock_task_service.claim_task.assert_called_once_with(task_data.id)

        # Should have started execution (task added to running_tasks)
        assert len(worker.running_tasks) > 0

        # Wait for task to complete
        await asyncio.sleep(0.2)

    @pytest.mark.anyio
    async def test_process_pending_tasks_skips_already_running(self) -> None:
        """Test that already running tasks are skipped."""
        worker = Worker(register_signals=False)

        # Mock task service
        mock_task_service = AsyncMock()
        mock_container = _make_mock_container(mock_task_service)

        task_id = uuid4()
        task_data = MagicMock()
        task_data.id = task_id
        task_data.function = "test_job"
        task_data.data = {}

        mock_task_service.get_pending_tasks.return_value = [task_data]

        # Mark task as already running
        worker.running_tasks[str(task_id)] = AsyncMock()

        worker.container = mock_container

        await worker._process_pending_tasks()

        # Should not try to claim the task
        mock_task_service.claim_task.assert_not_called()

    @pytest.mark.anyio
    async def test_process_pending_tasks_claim_fails(self) -> None:
        """Test handling when task claim fails (another worker claimed it)."""
        worker = Worker(register_signals=False)

        # Mock task service
        mock_task_service = AsyncMock()
        mock_task_service.claim_task.return_value = False  # Claim failed
        mock_container = _make_mock_container(mock_task_service)

        task_data = MagicMock()
        task_data.id = uuid4()
        task_data.function = "test_job"
        task_data.data = {}

        mock_task_service.get_pending_tasks.return_value = [task_data]

        worker.container = mock_container

        await worker._process_pending_tasks()

        # Should have tried to claim
        mock_task_service.claim_task.assert_called_once()

        # Should not have started execution
        assert len(worker.running_tasks) == 0


class TestWorkerCleanup:
    """Test Worker cleanup on shutdown."""

    @pytest.mark.anyio
    async def test_cleanup_cancels_running_tasks(self) -> None:
        """Test that cleanup cancels all running tasks."""
        worker = Worker(register_signals=False)

        # Create real asyncio tasks
        async def long_task() -> None:
            await asyncio.sleep(10)

        task1 = asyncio.create_task(long_task())
        task2 = asyncio.create_task(long_task())

        worker.running_tasks = {"task-1": task1, "task-2": task2}

        # Mock cleanup dependencies
        mock_task_service = AsyncMock()
        worker.container = _make_mock_container(mock_task_service)
        worker._channels_backend = AsyncMock()
        worker._heartbeat_manager = AsyncMock()
        worker._log_buffer = MagicMock()
        worker._log_buffer.flush = AsyncMock()

        # Run cleanup
        await worker._cleanup()

        # Tasks should be cancelled
        assert task1.cancelled() or task1.done()
        assert task2.cancelled() or task2.done()

    @pytest.mark.anyio
    async def test_cleanup_waits_for_tasks(self) -> None:
        """Test that cleanup waits for tasks to complete."""
        worker = Worker(register_signals=False)

        # Create real tasks that complete quickly
        async def quick_task() -> None:
            await asyncio.sleep(0.01)

        task1 = asyncio.create_task(quick_task())
        task2 = asyncio.create_task(quick_task())

        worker.running_tasks = {"task-1": task1, "task-2": task2}

        # Mock cleanup dependencies
        mock_task_service = AsyncMock()
        worker.container = _make_mock_container(mock_task_service)
        worker._channels_backend = AsyncMock()
        worker._heartbeat_manager = AsyncMock()
        worker._log_buffer = MagicMock()
        worker._log_buffer.flush = AsyncMock()

        # Run cleanup
        await worker._cleanup()

        # Tasks should be done
        assert task1.done()
        assert task2.done()

    @pytest.mark.anyio
    async def test_cleanup_timeout(self) -> None:
        """Test that cleanup times out if tasks don't complete."""
        worker = Worker(shutdown_timeout=0.1, register_signals=False)  # Very short timeout

        # Create task that never completes
        async def long_task() -> None:
            await asyncio.sleep(10)

        task = asyncio.create_task(long_task())
        worker.running_tasks = {"task-1": task}

        # Mock cleanup dependencies
        mock_task_service = AsyncMock()
        worker.container = _make_mock_container(mock_task_service)
        worker._channels_backend = AsyncMock()
        worker._heartbeat_manager = AsyncMock()
        worker._log_buffer = MagicMock()
        worker._log_buffer.flush = AsyncMock()

        # Run cleanup
        await worker._cleanup()

        # Should not raise error, just timeout
        # Task will be cancelled
        assert task.cancelled() or task.done()


class TestWorkerIntegrationMocks:
    """Integration-style tests with mocked dependencies."""

    @pytest.mark.anyio
    async def test_worker_run_loop_exits_on_shutdown(self) -> None:
        """Test that worker loop exits when shutdown is signaled."""
        worker = Worker(poll_interval=0.1, register_signals=False)

        # Mock task service
        mock_task_service = AsyncMock()
        mock_task_service.get_pending_tasks.return_value = []
        mock_task_service.requeue_stale_running = AsyncMock()
        mock_container = _make_mock_container(mock_task_service)

        worker.container = mock_container

        # Start worker loop in background
        async def run_and_shutdown() -> None:
            # Run worker in background
            worker_task = asyncio.create_task(worker._run())

            # Wait a bit
            await asyncio.sleep(0.2)

            # Signal shutdown
            worker.shutdown_event.set()

            # Wait for worker to exit
            await asyncio.wait_for(worker_task, timeout=1.0)

        await run_and_shutdown()

        # Worker should have polled at least once
        assert mock_task_service.get_pending_tasks.call_count >= 1

    @pytest.mark.anyio
    async def test_worker_processes_multiple_tasks(self) -> None:
        """Test that worker can process multiple tasks concurrently."""
        worker = Worker(poll_interval=0.1, batch_size=5, register_signals=False)

        # Mock task service
        mock_task_service = AsyncMock()
        mock_task_service.claim_task.return_value = True
        mock_container = _make_mock_container(mock_task_service)

        # Create multiple mock tasks
        tasks_data = []
        for i in range(3):
            task_data = MagicMock()
            task_data.id = uuid4()
            task_data.function = "concurrent_job"
            task_data.data = {"index": i}
            tasks_data.append(task_data)

        # Return tasks on first call, empty on subsequent calls
        call_count = 0

        def get_pending_side_effect(*args: Any, **kwargs: Any) -> list[Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return tasks_data
            return []

        mock_task_service.get_pending_tasks.side_effect = get_pending_side_effect

        # Register a job
        from sqlstack.lib.jobs import _job_registry

        execution_count = 0

        async def concurrent_job(index: int) -> dict:
            nonlocal execution_count
            execution_count += 1
            await asyncio.sleep(0.05)
            return {"index": index}

        _job_registry["concurrent_job"] = concurrent_job

        worker.container = mock_container
        worker._heartbeat_manager = MagicMock()
        worker._heartbeat_manager.register_job = MagicMock()
        worker._heartbeat_manager.unregister_job = MagicMock()

        await worker._process_pending_tasks()

        # Should have 3 tasks running
        assert len(worker.running_tasks) == 3

        # Wait for all tasks to complete
        await asyncio.sleep(0.3)

        # All tasks should have executed
        assert execution_count == 3

        # Cleanup should remove completed tasks
        worker._cleanup_completed_tasks()
        assert len(worker.running_tasks) == 0
