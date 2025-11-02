"""Task management service for background jobs using SQLSpec."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import structlog
from sqlspec import sql

from sqlstack import schemas as s
from sqlstack.services._base import OffsetPagination, SQLSpecService, StatementFilter

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = structlog.get_logger()


class TaskService(SQLSpecService):
    """Service for managing background tasks using SQLSpec."""

    async def create_task(
        self,
        function: str,
        data: dict[str, Any] | None = None,
        *,
        key: str | None = None,
        priority: int = 0,
        scheduled_at: datetime | None = None,
        max_retries: int = 3,
    ) -> UUID:
        """Create a new task or return existing if key exists.

        Args:
            function: Name of the function to execute
            data: Task data/arguments
            key: Unique key for deduplication
            priority: Task priority (higher = more important)
            scheduled_at: When to run the task (None = immediately)
            max_retries: Maximum retry attempts on failure

        Returns:
            Task ID
        """
        task_id = uuid4()
        status = "scheduled" if scheduled_at else "pending"

        task_data = {
            "id": task_id,
            "key": key,
            "function": function,
            "data": data or {},
            "status": status,
            "priority": priority,
            "scheduled_at": scheduled_at,
            "max_retries": max_retries,
        }

        if key:
            # Check if task with this key already exists
            existing = await self.driver.select_value_or_none(sql.select("id").from_("job").where_eq("key", key))
            if existing:
                await logger.ainfo("task with key already exists", task_id=str(existing), key=key)
                return UUID(str(existing))

        # Insert new task
        result = await self.driver.select_value(
            sql.insert("job").columns(*task_data.keys()).values(**task_data).returning("id")
        )
        task_id = UUID(str(result))

        await logger.ainfo("task created", task_id=str(task_id), function=function, key=key)

        return task_id

    async def get_pending_tasks(self, limit: int = 10) -> Sequence[s.Job]:
        """Get pending tasks ordered by priority and creation time.

        Note: Uses raw SQL for FOR UPDATE SKIP LOCKED since SQLSpec
        doesn't support it yet.

        Args:
            limit: Maximum number of tasks to retrieve

        Returns:
            List of task objects
        """
        # Use raw SQL for proper row locking (FOR UPDATE SKIP LOCKED)
        return await self.driver.select(
            """
            SELECT id, key, function, data, status, priority,
                   max_retries, retry_count, scheduled_at, created_at,
                   started_at, completed_at, error, result, metadata
            FROM job
            WHERE status = 'pending'
              AND (scheduled_at IS NULL OR scheduled_at <= :now)
            ORDER BY priority DESC, created_at ASC
            LIMIT :limit
            FOR UPDATE SKIP LOCKED
            """,
            now=datetime.now(UTC),
            limit=limit,
            schema_type=s.Job,
        )

    async def claim_task(self, task_id: UUID) -> bool:
        """Claim a task for processing (atomic operation).

        Uses SELECT FOR UPDATE SKIP LOCKED to prevent race conditions
        between multiple workers.

        Args:
            task_id: Task to claim

        Returns:
            True if successfully claimed, False if already claimed
        """
        # Use a transaction with SELECT FOR UPDATE to atomically claim the task
        async with self.begin_transaction():
            # Use raw SQL for FOR UPDATE (not yet supported by SQLSpec)
            locked_task = await self.driver.select_one_or_none(
                """
                SELECT id, status FROM job
                WHERE id = :task_id AND status IN ('pending', 'scheduled')
                FOR UPDATE SKIP LOCKED
                """,
                task_id=task_id,
            )
            if not locked_task:
                return False
            await self.driver.execute(
                sql.update("job").set(status="running", started_at=datetime.now(UTC)).where_eq("id", task_id)
            )

            return True

    async def complete_task(self, task_id: UUID, result: dict[str, Any] | None = None) -> None:
        """Mark task as completed.

        Args:
            task_id: Task to complete
            result: Task result data
        """
        await self.driver.execute(
            sql.update("job")
            .set(status="completed", completed_at=datetime.now(UTC), result=result or {})
            .where_eq("id", task_id)
        )

        await logger.ainfo("task completed", task_id=str(task_id))

    async def fail_task(self, task_id: UUID, error: str, retry: bool = True) -> None:
        """Mark task as failed.

        Args:
            task_id: Task that failed
            error: Error message
            retry: Whether to retry the task
        """
        # Atomically update the task status and retry count
        updated_task = await self.driver.select_one_or_none(
            """
            UPDATE job
            SET
                status = CASE
                    WHEN retry_count < max_retries AND :retry THEN 'pending'
                    ELSE 'failed'
                END,
                retry_count = CASE
                    WHEN retry_count < max_retries AND :retry THEN retry_count + 1
                    ELSE retry_count
                END,
                completed_at = CASE
                    WHEN retry_count >= max_retries OR NOT :retry THEN NOW()
                    ELSE completed_at
                END,
                started_at = CASE
                    WHEN retry_count < max_retries AND :retry THEN NULL
                    ELSE started_at
                END,
                error = :error
            WHERE id = :task_id
            RETURNING status, retry_count
            """,
            task_id=task_id,
            error=error,
            retry=retry,
        )

        if not updated_task:
            return

        if updated_task["status"] == "pending":
            await logger.ainfo(
                "task scheduled for retry", task_id=str(task_id), retry_count=updated_task["retry_count"]
            )
        else:
            await logger.aerror("task failed permanently", task_id=str(task_id), error=error)

    async def cancel_task(self, task_id: UUID) -> bool:
        """Cancel a pending task.

        Uses SELECT FOR UPDATE to ensure atomic cancellation.

        Args:
            task_id: Task to cancel

        Returns:
            True if cancelled, False if not found or already running
        """
        async with self.begin_transaction():
            # Use raw SQL for FOR UPDATE (not yet supported by SQLSpec)
            locked_task = await self.driver.select_one_or_none(
                """
                SELECT id, status FROM job
                WHERE id = :task_id AND status IN ('pending', 'scheduled')
                FOR UPDATE NOWAIT
                """,
                task_id=task_id,
            )

            if not locked_task:
                return False

            # Update the locked task
            await self.driver.execute(
                sql.update("job").set(status="cancelled", completed_at=datetime.now(UTC)).where_eq("id", task_id)
            )

            return True

    async def get_task(self, task_id: UUID) -> s.Job | None:
        """Get a single task by ID.

        Args:
            task_id: Task ID to retrieve

        Returns:
            Task object or None if not found
        """
        return await self.driver.select_one_or_none(
            sql.select(
                "id",
                "key",
                "function",
                "data",
                "status",
                "priority",
                "max_retries",
                "retry_count",
                "scheduled_at",
                "created_at",
                "started_at",
                "completed_at",
                "error",
                "result",
                "metadata",
            )
            .from_("job")
            .where_eq("id", task_id),
            schema_type=s.Job,
        )

    async def get_statistics(self) -> s.JobStats:
        """Get task queue statistics.

        Returns:
            JobStats object with counts by status
        """
        rows = await self.driver.select(sql.select("status", "COUNT(1) as count").from_("job").group_by("status"))

        stats_dict = {row["status"]: row["count"] for row in rows}
        total = sum(stats_dict.values())

        return s.JobStats(
            pending=stats_dict.get("pending", 0),
            running=stats_dict.get("running", 0),
            completed=stats_dict.get("completed", 0),
            failed=stats_dict.get("failed", 0),
            cancelled=stats_dict.get("cancelled", 0),
            scheduled=stats_dict.get("scheduled", 0),
            total=total,
        )

    async def list_tasks(self, *filters: StatementFilter, status: str | None = None) -> OffsetPagination[s.Job]:
        """List tasks with pagination and filtering.

        Args:
            filters: Additional filters
            status: Filter by status

        Returns:
            Paginated list of tasks
        """
        stmt = sql.select(
            "id",
            "key",
            "function",
            "data",
            "status",
            "priority",
            "max_retries",
            "retry_count",
            "scheduled_at",
            "created_at",
            "started_at",
            "completed_at",
            "error",
            "result",
            "metadata",
        ).from_("job")

        if status:
            stmt = stmt.where_eq("status", status)

        stmt = stmt.order_by("created_at DESC")

        return await self.paginate(stmt, *filters, schema_type=s.Job)

    async def cleanup_old_jobs(self, days: int = 30) -> int:
        """Clean up old completed jobs.

        Args:
            days: Days to keep completed jobs

        Returns:
            Number of jobs cleaned up
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days)
        result = await self.driver.select(
            """
            DELETE FROM job
            WHERE status IN ('completed', 'failed', 'cancelled')
              AND completed_at < :cutoff
            RETURNING id
            """,
            cutoff=cutoff_date,
        )

        count = len(result) if result else 0
        await logger.ainfo(f"cleaned up {count} old jobs")
        return count
