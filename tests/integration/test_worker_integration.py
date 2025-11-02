"""Integration tests for complete worker system."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from sqlstack.lib.jobs import get_job_registry, get_scheduled_jobs, register_job
from sqlstack.lib.worker import Worker
from sqlstack.services import TaskService

if TYPE_CHECKING:
    from sqlspec.adapters.asyncpg import AsyncpgDriver


@pytest.fixture
def task_service(driver: AsyncpgDriver) -> TaskService:
    """Provide TaskService fixture."""
    return TaskService(driver)


class TestWorkerIntegration:
    """Integration tests for Worker with real database."""

    @pytest.mark.anyio
    async def test_worker_executes_task_end_to_end(self, task_service: TaskService, clean_database: None) -> None:
        """Test complete task execution flow."""
        # Register a test job
        execution_record: dict = {}

        @register_job(name="integration_test_job")
        async def integration_test_job(value: str) -> dict:
            execution_record["executed"] = True
            execution_record["value"] = value
            return {"result": value.upper()}

        # Create a task
        task_id = await task_service.create_task(function="integration_test_job", data={"value": "test"})

        # Initialize worker
        worker = Worker(poll_interval=0.1)
        worker.task_service = task_service

        # Process one batch of tasks
        await worker._process_pending_tasks()

        # Wait for task to complete
        await asyncio.sleep(0.2)

        # Verify task was executed
        assert execution_record.get("executed") is True
        assert execution_record.get("value") == "test"

        # Verify task status in database
        task = await task_service.get_task(task_id)
        assert task is not None
        assert task.status == "completed"
        assert task.result == {"result": {"result": "TEST"}}

    @pytest.mark.anyio
    async def test_worker_handles_task_failure(self, task_service: TaskService, clean_database: None) -> None:
        """Test worker handling of task failures."""

        @register_job(name="failing_integration_job")
        async def failing_integration_job() -> dict[str, Any]:
            msg = "Intentional test failure"
            raise ValueError(msg)

        # Create a task
        task_id = await task_service.create_task(function="failing_integration_job", max_retries=2)

        # Initialize worker
        worker = Worker(poll_interval=0.1)
        worker.task_service = task_service

        # Process task
        await worker._process_pending_tasks()
        await asyncio.sleep(0.2)

        # Task should be pending (for retry)
        task = await task_service.get_task(task_id)
        assert task is not None
        assert task.status == "pending"
        assert task.retry_count == 1
        assert task.error is not None
        assert "Intentional test failure" in task.error

        # Process retry
        await worker._process_pending_tasks()
        await asyncio.sleep(0.2)

        # Check retry count increased
        task = await task_service.get_task(task_id)
        assert task.retry_count == 2

    @pytest.mark.anyio
    async def test_worker_respects_task_priority(self, task_service: TaskService, clean_database: None) -> None:
        """Test that worker processes high-priority tasks first."""
        execution_order: list = []

        @register_job(name="priority_test_job")
        async def priority_test_job(label: str) -> dict:
            execution_order.append(label)
            await asyncio.sleep(0.05)
            return {"label": label}

        # Create tasks with different priorities
        await task_service.create_task(function="priority_test_job", data={"label": "low"}, priority=1)
        await task_service.create_task(function="priority_test_job", data={"label": "high"}, priority=10)
        await task_service.create_task(function="priority_test_job", data={"label": "medium"}, priority=5)

        # Initialize worker
        worker = Worker(poll_interval=0.1, batch_size=10)
        worker.task_service = task_service

        # Process all tasks
        await worker._process_pending_tasks()
        await asyncio.sleep(0.3)

        # Should execute in priority order (high to low)
        assert len(execution_order) == 3
        assert execution_order[0] == "high"
        assert execution_order[1] == "medium"
        assert execution_order[2] == "low"

    @pytest.mark.anyio
    async def test_worker_concurrent_task_execution(self, task_service: TaskService, clean_database: None) -> None:
        """Test worker executing multiple tasks concurrently."""
        execution_times: dict = {}

        @register_job(name="concurrent_test_job")
        async def concurrent_test_job(task_id: str) -> dict:
            start = datetime.now(UTC)
            await asyncio.sleep(0.1)
            end = datetime.now(UTC)
            execution_times[task_id] = (start, end)
            return {"task_id": task_id}

        # Create multiple tasks
        for i in range(3):
            await task_service.create_task(function="concurrent_test_job", data={"task_id": f"task_{i}"})

        # Initialize worker
        worker = Worker(poll_interval=0.1, batch_size=10)
        worker.task_service = task_service

        # Process tasks
        start_time = datetime.now(UTC)
        await worker._process_pending_tasks()
        await asyncio.sleep(0.3)
        end_time = datetime.now(UTC)

        # All 3 tasks should have executed
        assert len(execution_times) == 3

        # Total time should be less than if they ran sequentially
        # (3 tasks * 0.1s = 0.3s sequentially, but should be ~0.1s concurrently)
        total_time = (end_time - start_time).total_seconds()
        assert total_time < 0.25  # Less than sequential execution

    @pytest.mark.anyio
    async def test_worker_scheduled_task_not_run_early(self, task_service: TaskService, clean_database: None) -> None:
        """Test that scheduled tasks don't run before their scheduled time."""
        execution_record: dict = {}

        @register_job(name="scheduled_test_job")
        async def scheduled_test_job() -> dict:
            execution_record["executed"] = True
            return {"status": "ok"}

        # Create task scheduled 1 hour in future
        await task_service.create_task(
            function="scheduled_test_job", scheduled_at=datetime.now(UTC) + timedelta(hours=1)
        )

        # Initialize worker
        worker = Worker(poll_interval=0.1)
        worker.task_service = task_service

        # Process tasks
        await worker._process_pending_tasks()
        await asyncio.sleep(0.2)

        # Task should NOT have executed
        assert execution_record.get("executed") is None

    @pytest.mark.anyio
    async def test_worker_atomic_task_claiming(self, task_service: TaskService, clean_database: None) -> None:
        """Test that multiple workers don't execute the same task."""
        execution_count: dict = {"count": 0}
        lock = asyncio.Lock()

        @register_job(name="atomic_test_job")
        async def atomic_test_job() -> dict:
            async with lock:
                execution_count["count"] += 1
            await asyncio.sleep(0.05)
            return {"status": "ok"}

        # Create a single task
        await task_service.create_task(function="atomic_test_job")

        # Create two workers
        worker1 = Worker(poll_interval=0.1)
        worker1.task_service = task_service

        worker2 = Worker(poll_interval=0.1)
        worker2.task_service = task_service

        # Both workers try to process tasks concurrently
        await asyncio.gather(worker1._process_pending_tasks(), worker2._process_pending_tasks())

        await asyncio.sleep(0.2)

        # Task should only execute once
        assert execution_count["count"] == 1

    @pytest.mark.anyio
    async def test_worker_key_deduplication(self, task_service: TaskService, clean_database: None) -> None:
        """Test that tasks with same key are deduplicated."""
        execution_count: dict = {"count": 0}

        @register_job(name="dedup_test_job")
        async def dedup_test_job() -> dict:
            execution_count["count"] += 1
            return {"status": "ok"}

        # Create multiple tasks with same key
        key = "unique-dedup-key"
        task_id1 = await task_service.create_task(function="dedup_test_job", key=key)
        task_id2 = await task_service.create_task(function="dedup_test_job", key=key)

        # Should be the same task
        assert task_id1 == task_id2

        # Initialize worker
        worker = Worker(poll_interval=0.1)
        worker.task_service = task_service

        # Process tasks
        await worker._process_pending_tasks()
        await asyncio.sleep(0.2)

        # Should only execute once
        assert execution_count["count"] == 1


class TestScheduledJobsIntegration:
    """Integration tests for scheduled jobs."""

    def setup_method(self) -> None:
        """Clear job registries before each test."""
        from sqlstack.lib.jobs import _job_registry, _schedule_registry

        _job_registry.clear()
        _schedule_registry.clear()

    @pytest.mark.anyio
    async def test_scheduled_job_registration(self, clean_database: None) -> None:
        """Test that scheduled jobs are registered correctly."""

        @register_job(cron="0 2 * * *")
        async def nightly_cleanup() -> dict:
            return {"status": "ok"}

        schedules = get_scheduled_jobs()

        assert "nightly_cleanup" in schedules
        assert schedules["nightly_cleanup"].cron == "0 2 * * *"

    @pytest.mark.anyio
    async def test_scheduled_job_next_run_calculation(self, clean_database: None) -> None:
        """Test next run time calculation for scheduled jobs."""

        @register_job(cron="0 14 * * *")  # Daily at 2 PM
        async def afternoon_task() -> dict:
            return {"status": "ok"}

        registry = get_job_registry()
        job_func = registry["afternoon_task"]

        assert hasattr(job_func, "__schedule_config__")
        config = job_func.__schedule_config__  # pyright: ignore

        # Calculate next run from midnight
        current = datetime(2024, 1, 15, 0, 0, 0, tzinfo=UTC)
        next_run = config.get_next_run(current)

        assert next_run.hour == 14
        assert next_run.minute == 0

    @pytest.mark.anyio
    async def test_interval_job_registration(self, clean_database: None) -> None:
        """Test that interval-based jobs are registered."""

        @register_job(interval=3600)  # Every hour
        async def hourly_sync() -> dict:
            return {"status": "ok"}

        schedules = get_scheduled_jobs()

        assert "hourly_sync" in schedules
        assert schedules["hourly_sync"].interval == 3600


class TestWorkerPluginIntegration:
    """Integration tests for WorkerPlugin."""

    @pytest.mark.anyio
    async def test_worker_plugin_discovers_jobs(self, clean_database: None) -> None:
        """Test that WorkerPlugin discovers job modules."""
        # Clear registries
        from sqlstack.lib.jobs import _discovered_modules, _job_registry, _schedule_registry, discover_jobs

        _discovered_modules.clear()
        _job_registry.clear()
        _schedule_registry.clear()

        # Discover jobs
        discover_jobs("sqlstack.server.jobs")

        registry = get_job_registry()
        schedules = get_scheduled_jobs()

        # Should have discovered system jobs
        assert "system_upkeep" in registry
        assert "background_worker_task" in registry
        assert "system_task" in registry
        assert "cleanup_old_sessions" in registry

        # cleanup_old_sessions should be scheduled
        assert "cleanup_old_sessions" in schedules

    @pytest.mark.anyio
    async def test_system_jobs_execute(self, task_service: TaskService, clean_database: None) -> None:
        """Test that discovered system jobs can execute."""
        from sqlstack.lib.jobs import discover_jobs

        # Discover jobs
        discover_jobs("sqlstack.server.jobs")

        # Create task for system_task (short duration job)
        task_id = await task_service.create_task(function="system_task")

        # Initialize worker
        worker = Worker(poll_interval=0.1)
        worker.task_service = task_service

        # Process task
        await worker._process_pending_tasks()

        # Wait for completion (system_task sleeps for 2 seconds)
        await asyncio.sleep(2.5)

        # Verify task completed
        task = await task_service.get_task(task_id)
        assert task is not None
        assert task.status == "completed"
        assert task.result is not None
        assert task.result["result"]["duration_seconds"] == 2


class TestWorkerCleanupIntegration:
    """Integration tests for worker cleanup functionality."""

    @pytest.mark.anyio
    async def test_cleanup_old_jobs_integration(
        self, task_service: TaskService, clean_database: None, driver: AsyncpgDriver
    ) -> None:
        """Test cleanup functionality with real database."""
        from sqlspec import sql

        # Create and complete multiple tasks
        task_ids = []
        for i in range(5):
            task_id = await task_service.create_task(function=f"cleanup_test_{i}")
            await task_service.claim_task(task_id)
            await task_service.complete_task(task_id)
            task_ids.append(task_id)

        # Make some tasks old
        old_date = datetime.now(UTC) - timedelta(days=60)
        for task_id in task_ids[:3]:
            await driver.execute(sql.update("job").set(completed_at=old_date).where_eq("id", task_id))

        # Cleanup old jobs
        count = await task_service.cleanup_old_jobs(days=30)

        assert count == 3

        # Verify old jobs removed
        for task_id in task_ids[:3]:
            task = await task_service.get_task(task_id)
            assert task is None

        # Verify recent jobs remain
        for task_id in task_ids[3:]:
            task = await task_service.get_task(task_id)
            assert task is not None


class TestWorkerErrorHandling:
    """Integration tests for worker error handling."""

    @pytest.mark.anyio
    async def test_worker_continues_after_task_error(self, task_service: TaskService, clean_database: None) -> None:
        """Test that worker continues processing after a task fails."""
        execution_record: dict = {"successful": []}

        @register_job(name="error_then_success_1")
        async def error_then_success_1() -> dict:
            msg = "First task fails"
            raise ValueError(msg)

        @register_job(name="error_then_success_2")
        async def error_then_success_2() -> dict:
            execution_record["successful"].append("task2")
            return {"status": "ok"}

        # Create failing task
        await task_service.create_task(function="error_then_success_1")

        # Create successful task
        await task_service.create_task(function="error_then_success_2")

        # Initialize worker
        worker = Worker(poll_interval=0.1)
        worker.task_service = task_service

        # Process both tasks
        await worker._process_pending_tasks()
        await asyncio.sleep(0.3)

        # Second task should have executed successfully
        assert "task2" in execution_record["successful"]

    @pytest.mark.anyio
    async def test_worker_handles_connection_errors(self, task_service: TaskService, clean_database: None) -> None:
        """Test worker handling of database connection errors."""
        worker = Worker(poll_interval=0.1)
        worker.task_service = task_service

        # Mock a connection error
        original_get_pending = task_service.get_pending_tasks

        async def mock_get_pending(*args: Any, **kwargs: Any) -> Any:
            # First call raises error, second call succeeds
            if not hasattr(mock_get_pending, "called"):
                mock_get_pending.called = True  # pyright: ignore
                msg = "Simulated connection error"
                raise ConnectionError(msg)
            return await original_get_pending(*args, **kwargs)

        with patch.object(task_service, "get_pending_tasks", side_effect=mock_get_pending):
            # Should not raise, should handle error gracefully
            await worker._run()
            await asyncio.sleep(0.3)

        # Worker should still be functional after error
        assert worker.task_service is not None
