"""Integration tests for TaskService."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from sqlspec import sql

from sqlstack.domain.system.services import TaskService
from sqlstack.lib.service import LimitOffsetFilter

if TYPE_CHECKING:
    from sqlspec.adapters.asyncpg import AsyncpgDriver


@pytest.fixture
def task_service(driver: AsyncpgDriver) -> TaskService:
    """Provide TaskService fixture."""
    return TaskService(driver)


class TestTaskServiceCreate:
    """Test TaskService.create_task method."""

    @pytest.mark.anyio
    async def test_create_task_basic(self, task_service: TaskService, clean_database: None) -> None:
        """Test creating a basic task."""
        task_id = await task_service.create_task(function="test_function", data={"param1": "value1", "param2": 42})

        assert isinstance(task_id, UUID)

        # Verify task was created
        task = await task_service.get_task(task_id)
        assert task is not None
        assert task.function == "test_function"
        assert task.data == {"param1": "value1", "param2": 42}
        assert task.status == "pending"
        assert task.priority == 0
        assert task.max_retries == 3

    @pytest.mark.anyio
    async def test_create_task_with_key(self, task_service: TaskService, clean_database: None) -> None:
        """Test creating task with unique key for deduplication."""
        key = "unique-task-key"

        # Create first task
        task_id1 = await task_service.create_task(function="test_function", data={"value": 1}, key=key)

        # Create second task with same key
        task_id2 = await task_service.create_task(function="test_function", data={"value": 2}, key=key)

        # Should return the same task ID
        assert task_id1 == task_id2

        # Verify only one task exists
        task = await task_service.get_task(task_id1)
        assert task is not None
        assert task.key == key
        assert task.data == {"value": 1}  # Original data preserved

    @pytest.mark.anyio
    async def test_create_task_with_priority(self, task_service: TaskService, clean_database: None) -> None:
        """Test creating task with custom priority."""
        task_id = await task_service.create_task(function="high_priority_task", priority=10)

        task = await task_service.get_task(task_id)
        assert task is not None
        assert task.priority == 10

    @pytest.mark.anyio
    async def test_create_task_scheduled(self, task_service: TaskService, clean_database: None) -> None:
        """Test creating scheduled task."""
        scheduled_at = datetime.now(UTC) + timedelta(hours=1)

        task_id = await task_service.create_task(function="scheduled_task", scheduled_at=scheduled_at)

        task = await task_service.get_task(task_id)
        assert task is not None
        assert task.status == "scheduled"
        assert task.scheduled_at is not None

    @pytest.mark.anyio
    async def test_create_task_with_max_retries(self, task_service: TaskService, clean_database: None) -> None:
        """Test creating task with custom max retries."""
        task_id = await task_service.create_task(function="retry_task", max_retries=5)

        task = await task_service.get_task(task_id)
        assert task is not None
        assert task.max_retries == 5


class TestTaskServiceGetPendingTasks:
    """Test TaskService.get_pending_tasks method."""

    @pytest.mark.anyio
    async def test_get_pending_tasks_empty(self, task_service: TaskService, clean_database: None) -> None:
        """Test getting pending tasks when none exist."""
        tasks = await task_service.get_pending_tasks()

        assert isinstance(tasks, list)
        assert len(tasks) == 0

    @pytest.mark.anyio
    async def test_get_pending_tasks_returns_pending(self, task_service: TaskService, clean_database: None) -> None:
        """Test that only pending tasks are returned."""
        # Create pending task
        pending_id = await task_service.create_task(function="pending_task")

        # Create scheduled task (not yet ready)
        await task_service.create_task(function="scheduled_task", scheduled_at=datetime.now(UTC) + timedelta(hours=1))

        # Get pending tasks
        tasks = await task_service.get_pending_tasks()

        assert len(tasks) == 1
        assert tasks[0].id == pending_id
        assert tasks[0].status == "pending"

    @pytest.mark.anyio
    async def test_get_pending_tasks_ordered_by_priority(self, task_service: TaskService, clean_database: None) -> None:
        """Test that pending tasks are ordered by priority (high to low)."""
        # Create tasks with different priorities
        low_priority = await task_service.create_task(function="low", priority=1)
        high_priority = await task_service.create_task(function="high", priority=10)
        medium_priority = await task_service.create_task(function="medium", priority=5)

        # Get pending tasks
        tasks = await task_service.get_pending_tasks()

        assert len(tasks) == 3
        # Should be ordered by priority DESC
        assert tasks[0].id == high_priority
        assert tasks[1].id == medium_priority
        assert tasks[2].id == low_priority

    @pytest.mark.anyio
    async def test_get_pending_tasks_limit(self, task_service: TaskService, clean_database: None) -> None:
        """Test limiting number of pending tasks returned."""
        # Create 5 tasks
        for i in range(5):
            await task_service.create_task(function=f"task_{i}")

        # Get only 3 tasks
        tasks = await task_service.get_pending_tasks(limit=3)

        assert len(tasks) == 3

    @pytest.mark.anyio
    async def test_get_pending_tasks_only_returns_pending_status(
        self, task_service: TaskService, clean_database: None
    ) -> None:
        """Test that get_pending_tasks only returns tasks with pending status."""
        # Create task with pending status (immediate)
        pending_task = await task_service.create_task(function="pending_task")

        # Create task with scheduled status (future)
        await task_service.create_task(function="scheduled_task", scheduled_at=datetime.now(UTC) + timedelta(hours=1))

        # Create task with scheduled status (past - but still 'scheduled' status)
        await task_service.create_task(
            function="past_scheduled_task", scheduled_at=datetime.now(UTC) - timedelta(minutes=1)
        )

        # Get pending tasks
        tasks = await task_service.get_pending_tasks()

        # Should return pending tasks AND scheduled tasks whose time has passed
        # - pending_task: status='pending', ready to run
        # - past_scheduled_task: status='scheduled' but scheduled_at <= now, ready to run
        # - scheduled_task: status='scheduled' with future time, NOT ready to run
        assert len(tasks) == 2
        task_ids = {t.id for t in tasks}
        assert pending_task in task_ids


class TestTaskServiceClaimTask:
    """Test TaskService.claim_task method."""

    @pytest.mark.anyio
    async def test_claim_task_success(self, task_service: TaskService, clean_database: None) -> None:
        """Test successfully claiming a pending task."""
        task_id = await task_service.create_task(function="test_task")

        # Claim the task
        claimed = await task_service.claim_task(task_id)

        assert claimed is True

        # Verify task status changed to running
        task = await task_service.get_task(task_id)
        assert task is not None
        assert task.status == "running"
        assert task.started_at is not None

    @pytest.mark.anyio
    async def test_claim_task_already_running(self, task_service: TaskService, clean_database: None) -> None:
        """Test claiming task that is already running."""
        task_id = await task_service.create_task(function="test_task")

        # Claim once
        await task_service.claim_task(task_id)

        # Try to claim again
        claimed = await task_service.claim_task(task_id)

        assert claimed is False

    @pytest.mark.anyio
    async def test_claim_task_nonexistent(self, task_service: TaskService, clean_database: None) -> None:
        """Test claiming non-existent task."""
        fake_id = uuid4()

        claimed = await task_service.claim_task(fake_id)

        assert claimed is False

    @pytest.mark.anyio
    async def test_claim_task_prevents_double_claim(self, task_service: TaskService, clean_database: None) -> None:
        """Test that a task cannot be claimed twice sequentially."""
        task_id = await task_service.create_task(function="test_task")

        # First claim should succeed
        first_claim = await task_service.claim_task(task_id)
        assert first_claim is True

        # Second claim should fail
        second_claim = await task_service.claim_task(task_id)
        assert second_claim is False

        # Verify task is in running state
        task = await task_service.get_task(task_id)
        assert task is not None
        assert task.status == "running"


class TestTaskServiceCompleteTask:
    """Test TaskService.complete_task method."""

    @pytest.mark.anyio
    async def test_complete_task_success(self, task_service: TaskService, clean_database: None) -> None:
        """Test marking task as completed."""
        task_id = await task_service.create_task(function="test_task")
        await task_service.claim_task(task_id)

        # Complete the task
        await task_service.complete_task(task_id, result={"status": "success", "value": 42})

        # Verify task status
        task = await task_service.get_task(task_id)
        assert task is not None
        assert task.status == "completed"
        assert task.completed_at is not None
        assert task.result == {"status": "success", "value": 42}

    @pytest.mark.anyio
    async def test_complete_task_no_result(self, task_service: TaskService, clean_database: None) -> None:
        """Test completing task with no result."""
        task_id = await task_service.create_task(function="test_task")
        await task_service.claim_task(task_id)

        await task_service.complete_task(task_id)

        task = await task_service.get_task(task_id)
        assert task is not None
        assert task.status == "completed"
        assert task.result == {}


class TestTaskServiceFailTask:
    """Test TaskService.fail_task method."""

    @pytest.mark.anyio
    async def test_fail_task_with_retry(self, task_service: TaskService, clean_database: None) -> None:
        """Test failing task with retry (should become pending again)."""
        task_id = await task_service.create_task(function="test_task", max_retries=3)
        await task_service.claim_task(task_id)

        # Fail the task
        await task_service.fail_task(task_id, error="Test error", retry=True)

        # Verify task status
        task = await task_service.get_task(task_id)
        assert task is not None
        assert task.status == "pending"  # Should be pending again for retry
        assert task.retry_count == 1
        assert task.error == "Test error"
        assert task.started_at is None  # Reset for retry

    @pytest.mark.anyio
    async def test_fail_task_no_retry(self, task_service: TaskService, clean_database: None) -> None:
        """Test failing task without retry."""
        task_id = await task_service.create_task(function="test_task")
        await task_service.claim_task(task_id)

        # Fail without retry
        await task_service.fail_task(task_id, error="Fatal error", retry=False)

        # Verify task status
        task = await task_service.get_task(task_id)
        assert task is not None
        assert task.status == "failed"
        assert task.completed_at is not None
        assert task.error == "Fatal error"

    @pytest.mark.anyio
    async def test_fail_task_max_retries_exhausted(self, task_service: TaskService, clean_database: None) -> None:
        """Test that task fails permanently after max retries."""
        task_id = await task_service.create_task(function="test_task", max_retries=2)

        # Fail and retry twice
        for _ in range(2):
            await task_service.claim_task(task_id)
            await task_service.fail_task(task_id, error="Error", retry=True)

        # Task should still be pending after 2 failures
        task = await task_service.get_task(task_id)
        assert task.status == "pending"
        assert task.retry_count == 2

        # Fail one more time (3rd failure = max_retries reached)
        await task_service.claim_task(task_id)
        await task_service.fail_task(task_id, error="Error", retry=True)

        # Should now be permanently failed
        task = await task_service.get_task(task_id)
        assert task is not None
        assert task.status == "failed"
        assert task.retry_count == 2  # Retry count doesn't increment when max reached
        assert task.completed_at is not None


class TestTaskServiceCancelTask:
    """Test TaskService.cancel_task method."""

    @pytest.mark.anyio
    async def test_cancel_task_success(self, task_service: TaskService, clean_database: None) -> None:
        """Test canceling a pending task."""
        task_id = await task_service.create_task(function="test_task")

        # Cancel the task
        cancelled = await task_service.cancel_task(task_id)

        assert cancelled is True

        # Verify task status
        task = await task_service.get_task(task_id)
        assert task is not None
        assert task.status == "cancelled"
        assert task.completed_at is not None

    @pytest.mark.anyio
    async def test_cancel_task_already_running(self, task_service: TaskService, clean_database: None) -> None:
        """Test that running tasks cannot be cancelled."""
        task_id = await task_service.create_task(function="test_task")
        await task_service.claim_task(task_id)

        # Try to cancel running task
        cancelled = await task_service.cancel_task(task_id)

        assert cancelled is False

        # Task should still be running
        task = await task_service.get_task(task_id)
        assert task is not None
        assert task.status == "running"

    @pytest.mark.anyio
    async def test_cancel_task_nonexistent(self, task_service: TaskService, clean_database: None) -> None:
        """Test canceling non-existent task."""
        fake_id = uuid4()

        cancelled = await task_service.cancel_task(fake_id)

        assert cancelled is False

    @pytest.mark.anyio
    async def test_cancel_scheduled_task(self, task_service: TaskService, clean_database: None) -> None:
        """Test canceling scheduled task."""
        task_id = await task_service.create_task(
            function="test_task", scheduled_at=datetime.now(UTC) + timedelta(hours=1)
        )

        # Cancel the scheduled task
        cancelled = await task_service.cancel_task(task_id)

        assert cancelled is True

        task = await task_service.get_task(task_id)
        assert task is not None
        assert task.status == "cancelled"


class TestTaskServiceListTasks:
    """Test TaskService.list_tasks method."""

    @pytest.mark.anyio
    async def test_list_tasks_empty(self, task_service: TaskService, clean_database: None) -> None:
        """Test listing tasks when none exist."""
        result = await task_service.list_tasks(LimitOffsetFilter(limit=10, offset=0))

        assert result.total == 0
        assert len(result.items) == 0

    @pytest.mark.anyio
    async def test_list_tasks_pagination(self, task_service: TaskService, clean_database: None) -> None:
        """Test task listing with pagination."""
        # Create 10 tasks
        for i in range(10):
            await task_service.create_task(function=f"task_{i}")

        # Get first page (5 items)
        page1 = await task_service.list_tasks(LimitOffsetFilter(limit=5, offset=0))

        assert page1.total == 10
        assert len(page1.items) == 5

        # Get second page
        page2 = await task_service.list_tasks(LimitOffsetFilter(limit=5, offset=5))

        assert page2.total == 10
        assert len(page2.items) == 5

        # Should not overlap
        page1_ids = {task.id for task in page1.items}
        page2_ids = {task.id for task in page2.items}
        assert len(page1_ids & page2_ids) == 0

    @pytest.mark.anyio
    async def test_list_tasks_filter_by_status(self, task_service: TaskService, clean_database: None) -> None:
        """Test filtering tasks by status."""
        pending_id = await task_service.create_task(function="pending_task")
        running_id = await task_service.create_task(function="running_task")
        await task_service.claim_task(running_id)

        completed_id = await task_service.create_task(function="completed_task")
        await task_service.claim_task(completed_id)
        await task_service.complete_task(completed_id)

        # Filter by pending
        pending_tasks = await task_service.list_tasks(LimitOffsetFilter(limit=10, offset=0), status="pending")
        assert pending_tasks.total == 1
        assert pending_tasks.items[0].id == pending_id

        # Filter by running
        running_tasks = await task_service.list_tasks(LimitOffsetFilter(limit=10, offset=0), status="running")
        assert running_tasks.total == 1
        assert running_tasks.items[0].id == running_id

        # Filter by completed
        completed_tasks = await task_service.list_tasks(LimitOffsetFilter(limit=10, offset=0), status="completed")
        assert completed_tasks.total == 1
        assert completed_tasks.items[0].id == completed_id

    @pytest.mark.anyio
    async def test_list_tasks_ordered_by_created(self, task_service: TaskService, clean_database: None) -> None:
        """Test that tasks are ordered by created_at DESC."""
        # Create tasks with small delay
        task_ids = []
        for i in range(3):
            task_id = await task_service.create_task(function=f"task_{i}")
            task_ids.append(task_id)
            await asyncio.sleep(0.01)

        # List tasks
        result = await task_service.list_tasks(LimitOffsetFilter(limit=10, offset=0))

        # Should be in reverse order (newest first)
        assert result.items[0].id == task_ids[2]
        assert result.items[1].id == task_ids[1]
        assert result.items[2].id == task_ids[0]


class TestTaskServiceGetStatistics:
    """Test TaskService.get_statistics method."""

    @pytest.mark.anyio
    async def test_get_statistics_empty(self, task_service: TaskService, clean_database: None) -> None:
        """Test statistics when no tasks exist."""
        stats = await task_service.get_statistics()

        assert stats.pending == 0
        assert stats.running == 0
        assert stats.completed == 0
        assert stats.failed == 0
        assert stats.cancelled == 0
        assert stats.scheduled == 0
        assert stats.total == 0

    @pytest.mark.anyio
    async def test_get_statistics_mixed_statuses(self, task_service: TaskService, clean_database: None) -> None:
        """Test statistics with various task statuses."""
        # Create pending tasks
        for i in range(3):
            await task_service.create_task(function=f"pending_{i}")

        # Create running task
        running_id = await task_service.create_task(function="running")
        await task_service.claim_task(running_id)

        # Create completed tasks
        for i in range(2):
            task_id = await task_service.create_task(function=f"completed_{i}")
            await task_service.claim_task(task_id)
            await task_service.complete_task(task_id)

        # Create failed task
        failed_id = await task_service.create_task(function="failed")
        await task_service.claim_task(failed_id)
        await task_service.fail_task(failed_id, error="Error", retry=False)

        # Create cancelled task
        cancelled_id = await task_service.create_task(function="cancelled")
        await task_service.cancel_task(cancelled_id)

        # Create scheduled task
        await task_service.create_task(function="scheduled", scheduled_at=datetime.now(UTC) + timedelta(hours=1))

        # Get statistics
        stats = await task_service.get_statistics()

        assert stats.pending == 3
        assert stats.running == 1
        assert stats.completed == 2
        assert stats.failed == 1
        assert stats.cancelled == 1
        assert stats.scheduled == 1
        assert stats.total == 9


class TestTaskServiceCleanupOldJobs:
    """Test TaskService.cleanup_old_jobs method."""

    @pytest.mark.anyio
    async def test_cleanup_old_jobs_no_old_jobs(self, task_service: TaskService, clean_database: None) -> None:
        """Test cleanup when no old jobs exist."""
        # Create recent completed task
        task_id = await task_service.create_task(function="recent")
        await task_service.claim_task(task_id)
        await task_service.complete_task(task_id)

        # Cleanup jobs older than 30 days
        count = await task_service.cleanup_old_jobs(days=30)

        assert count == 0

    @pytest.mark.anyio
    async def test_cleanup_old_jobs_removes_old_completed(
        self, task_service: TaskService, clean_database: None, driver: AsyncpgDriver
    ) -> None:
        """Test cleanup removes old completed jobs."""

        # Create old completed task (manually set completed_at to old date)
        task_id = await task_service.create_task(function="old_task")
        await task_service.claim_task(task_id)
        await task_service.complete_task(task_id)

        # Update completed_at to 60 days ago
        old_date = datetime.now(UTC) - timedelta(days=60)
        await driver.execute(sql.update("job").set(completed_at=old_date).where_eq("id", task_id))

        # Cleanup jobs older than 30 days
        count = await task_service.cleanup_old_jobs(days=30)

        assert count == 1

        # Verify task was deleted
        task = await task_service.get_task(task_id)
        assert task is None

    @pytest.mark.anyio
    async def test_cleanup_old_jobs_preserves_recent(
        self, task_service: TaskService, clean_database: None, driver: AsyncpgDriver
    ) -> None:
        """Test cleanup preserves recent completed jobs."""

        # Create old task
        old_task_id = await task_service.create_task(function="old_task")
        await task_service.claim_task(old_task_id)
        await task_service.complete_task(old_task_id)

        old_date = datetime.now(UTC) - timedelta(days=60)
        await driver.execute(sql.update("job").set(completed_at=old_date).where_eq("id", old_task_id))

        # Create recent task
        recent_task_id = await task_service.create_task(function="recent_task")
        await task_service.claim_task(recent_task_id)
        await task_service.complete_task(recent_task_id)

        # Cleanup
        count = await task_service.cleanup_old_jobs(days=30)

        assert count == 1

        # Recent task should still exist
        recent_task = await task_service.get_task(recent_task_id)
        assert recent_task is not None

    @pytest.mark.anyio
    async def test_cleanup_old_jobs_removes_failed_and_cancelled(
        self, task_service: TaskService, clean_database: None, driver: AsyncpgDriver
    ) -> None:
        """Test cleanup removes old failed and cancelled jobs."""

        # Create old failed task
        failed_id = await task_service.create_task(function="failed_task")
        await task_service.claim_task(failed_id)
        await task_service.fail_task(failed_id, error="Error", retry=False)

        # Create old cancelled task
        cancelled_id = await task_service.create_task(function="cancelled_task")
        await task_service.cancel_task(cancelled_id)

        # Update to old dates
        old_date = datetime.now(UTC) - timedelta(days=60)
        await driver.execute(sql.update("job").set(completed_at=old_date).where_eq("id", failed_id))
        await driver.execute(sql.update("job").set(completed_at=old_date).where_eq("id", cancelled_id))

        # Cleanup
        count = await task_service.cleanup_old_jobs(days=30)

        assert count == 2

    @pytest.mark.anyio
    async def test_cleanup_old_jobs_preserves_pending(
        self, task_service: TaskService, clean_database: None, driver: AsyncpgDriver
    ) -> None:
        """Test cleanup does not remove pending/running jobs."""

        # Create old pending task
        pending_id = await task_service.create_task(function="pending_task")

        # Update created_at to old date
        old_date = datetime.now(UTC) - timedelta(days=60)
        await driver.execute(sql.update("job").set(created_at=old_date).where_eq("id", pending_id))

        # Cleanup
        count = await task_service.cleanup_old_jobs(days=30)

        assert count == 0

        # Pending task should still exist
        task = await task_service.get_task(pending_id)
        assert task is not None
