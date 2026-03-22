"""Task management service for background jobs using SQLSpec."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from sqlspec import sql
from sqlspec.utils.uuids import uuid7

from sqlstack.domain.system import schemas as s
from sqlstack.lib.log import log_error, log_info, log_warning
from sqlstack.lib.realtime import RealtimeEntityRef, RealtimeEvent
from sqlstack.lib.service import OffsetPagination, SQLSpecAsyncService, StatementFilter
from sqlstack.utils.serialization import schema_dump

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlstack.lib.realtime import RealtimePublisher

logger = structlog.get_logger()
_PUBLISH_ERRORS = (OSError, RuntimeError, ValueError, TypeError)


class TaskService(SQLSpecAsyncService):
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
        team_id: UUID | None = None,
    ) -> UUID:
        """Create a new task or return existing if key exists.

        Args:
            function: Name of the function to execute
            data: Task data/arguments
            key: Unique key for deduplication
            priority: Task priority (higher = more important)
            scheduled_at: When to run the task (None = immediately)
            max_retries: Maximum retry attempts on failure
            team_id: Optional team ID for scoping

        Returns:
            Task ID
        """
        task_id = uuid7()
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

        if team_id:
            task_data["data"]["team_id"] = str(team_id)

        is_scheduled_key = bool(key and key.startswith("scheduled-"))

        if key:
            # Check if task with this key already exists
            existing = await self.driver.select_value_or_none(sql.select("id").from_("job").where_eq("key", key))
            if existing:
                if is_scheduled_key:
                    await logger.adebug(
                        "scheduled job already registered; reusing existing task",
                        task_id=str(existing),
                        schedule_key=key,
                        job_name=key.removeprefix("scheduled-"),
                    )
                else:
                    await logger.adebug(
                        "task key already exists; reusing existing task", task_id=str(existing), task_key=key
                    )
                return UUID(str(existing))

        # Insert new task
        result = await self.driver.select_value(
            sql.insert("job").columns(*task_data.keys()).values(**task_data).returning("id")
        )
        task_id = UUID(str(result))

        if is_scheduled_key:
            await logger.adebug(
                "registered scheduled job task", task_id=str(task_id), schedule_key=key, job_name=function
            )
        else:
            await log_info("task queued", task_id=str(task_id), function=function, key=key)

        # Notify worker of new task via PostgreSQL LISTEN/NOTIFY
        await self._notify_worker("new_task", str(task_id))

        return task_id

    async def get_pending_tasks(self, limit: int = 10) -> Sequence[s.Job]:
        """Get pending tasks ordered by priority and creation time.

        Args:
            limit: Maximum number of tasks to retrieve

        Returns:
            List of task objects
        """
        return await self.driver.select(
            """
            SELECT id, key, function, data, status, priority,
                   max_retries, retry_count, scheduled_at, created_at,
                   started_at, heartbeat_at, completed_at, error, result, metadata
            FROM job
            WHERE status IN ('pending', 'scheduled')
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

        Args:
            task_id: Task to claim

        Returns:
            True if successfully claimed, False if already claimed
        """
        now = datetime.now(UTC)
        async with self.begin_transaction():
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
                sql.update("job").set(status="running", started_at=now, heartbeat_at=now).where_eq("id", task_id)
            )

            return True

    async def complete_task(self, task_id: UUID, result: dict[str, Any] | None = None) -> None:
        """Mark task as completed.

        Args:
            task_id: Task to complete
            result: Task result data
        """
        now = datetime.now(UTC)
        await self.driver.execute(
            sql
            .update("job")
            .set(status="completed", completed_at=now, heartbeat_at=now, result=result or {})
            .where_eq("id", task_id)
        )

        await log_info("task completed", task_id=str(task_id))

    async def fail_task(self, task_id: UUID, error: str, retry: bool = True) -> None:
        """Mark task as failed.

        Args:
            task_id: Task that failed
            error: Error message
            retry: Whether to retry the task
        """
        updated_task = await self.driver.select_one_or_none(
            """
            WITH ctx AS (
                SELECT :retry::boolean AS should_retry
            )
            UPDATE job
            SET
                status = CASE
                    WHEN retry_count < max_retries AND ctx.should_retry THEN 'pending'
                    ELSE 'failed'
                END,
                retry_count = CASE
                    WHEN retry_count < max_retries AND ctx.should_retry THEN retry_count + 1
                    ELSE retry_count
                END,
                completed_at = CASE
                    WHEN retry_count >= max_retries OR NOT ctx.should_retry THEN NOW()
                    ELSE completed_at
                END,
                started_at = CASE
                    WHEN retry_count < max_retries AND ctx.should_retry THEN NULL
                    ELSE started_at
                END,
                error = :error
            FROM ctx
            WHERE job.id = :task_id
            RETURNING job.status, job.retry_count
            """,
            task_id=task_id,
            error=error,
            retry=retry,
        )

        if not updated_task:
            return

        if updated_task["status"] == "pending":
            await log_info(
                "task scheduled for retry", task_id=str(task_id), retry_count=updated_task["retry_count"]
            )
        else:
            await log_error("task failed permanently", task_id=str(task_id), error=error)

    async def reschedule_job(self, function: str, schedule_config: dict[str, Any], completed_at: datetime) -> UUID:
        """Create the next execution of a scheduled job."""
        from sqlstack.lib.jobs import ScheduleConfig

        config = ScheduleConfig(**schedule_config)
        next_run = config.get_next_run(after=completed_at)
        key = f"scheduled-{function}"

        # Clear key on old terminal jobs so the new one can claim it
        await self.driver.execute(
            "UPDATE job SET key = NULL WHERE key = :key AND status IN ('completed', 'failed', 'cancelled')", key=key
        )

        return await self.create_task(
            function=function,
            data={"_scheduled": True, "_schedule_config": schedule_config},
            scheduled_at=next_run,
            key=key,
            priority=5,
        )

    async def cancel_task(self, task_id: UUID) -> bool:
        """Cancel a pending task."""
        async with self.begin_transaction():
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

            await self.driver.execute(
                sql.update("job").set(status="cancelled", completed_at=datetime.now(UTC)).where_eq("id", task_id)
            )

            return True

    async def get_task(self, task_id: UUID) -> s.Job | None:
        """Get a single task by ID."""
        return await self.driver.select_one_or_none(
            sql
            .select(
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
                "heartbeat_at",
                "completed_at",
                "error",
                "result",
                "metadata",
            )
            .from_("job")
            .where_eq("id", task_id),
            schema_type=s.Job,
        )

    async def get_statistics(self) -> dict[str, int]:
        """Get task queue statistics."""
        rows = await self.driver.select(sql.select("status", "COUNT(1) as count").from_("job").group_by("status"))

        stats = {row["status"]: row["count"] for row in rows}
        for key in ("pending", "scheduled", "running", "completed", "failed"):
            stats.setdefault(key, 0)

        return stats

    async def list_tasks(self, *filters: StatementFilter, status: str | None = None) -> OffsetPagination[s.Job]:
        """List tasks with pagination and filtering."""
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
            "heartbeat_at",
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
        """Clean up old completed jobs."""
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
        await log_info(f"cleaned up {count} old jobs")
        return count

    async def requeue_stale_running(self, stale_after: timedelta = timedelta(minutes=5)) -> int:
        """Requeue tasks that were left in 'running' due to a crash."""
        cutoff = datetime.now(UTC) - stale_after
        rows = await self.driver.select(
            """
            UPDATE job
            SET status = 'pending',
                started_at = NULL,
                heartbeat_at = NULL,
                completed_at = NULL,
                retry_count = retry_count + 1,
                error = COALESCE(error, 'Recovered from worker crash')
            WHERE status = 'running'
              AND (heartbeat_at IS NULL OR heartbeat_at < :cutoff)
            RETURNING id
            """,
            cutoff=cutoff,
        )

        count = len(rows) if rows else 0
        if count:
            task_ids = [str(r["id"]) for r in rows]
            await log_warning("requeued stale running tasks", count=count, task_ids=task_ids)
        return count

    async def touch_heartbeat(self, task_id: UUID) -> None:
        """Update heartbeat timestamp for a running task."""
        await self.driver.execute(
            sql.update("job").set(heartbeat_at=datetime.now(UTC)).where_eq("id", task_id).where_eq("status", "running")
        )

    async def null_heartbeats(self, task_ids: list[UUID]) -> None:
        """Null heartbeat_at for specific tasks."""
        if not task_ids:
            return
        await self.driver.execute(
            "UPDATE job SET heartbeat_at = NULL WHERE id = ANY(:ids::uuid[]) AND status = 'running'", ids=task_ids
        )

    # ── Job Log Methods ──────────────────────────────────────────────

    def _job_log_table(self, data: s.JobLogCreate) -> str:
        """Determine the target table based on scoping fields."""
        if data.team_id is not None:
            return "team_job_log"
        return "job_log"

    def _job_log_columns(self, data: s.JobLogCreate) -> dict[str, Any]:
        """Build the column dict for the target table."""
        row: dict[str, Any] = schema_dump(data)
        row["id"] = uuid7()
        return row

    async def _publish_job_log_event(
        self, log_entry: s.JobLog, team_id: UUID, publisher: RealtimePublisher
    ) -> None:
        """Publish a single job log event to the team channel."""
        payload = {
            "log_id": str(log_entry.id),
            "job_id": str(log_entry.job_id) if log_entry.job_id else None,
            "stage": log_entry.stage,
            "level": log_entry.level,
            "message": log_entry.message,
            "detail": log_entry.detail,
            "sequence": log_entry.sequence,
            "duration_ms": log_entry.duration_ms,
            "team_id": str(team_id),
            "created_at": log_entry.created_at.isoformat() if log_entry.created_at else datetime.now(UTC).isoformat(),
        }
        try:
            event = RealtimeEvent(
                event_type="team.job.log.created",
                scope="team",
                team_id=team_id,
                entity=RealtimeEntityRef(type="job_log", id=str(log_entry.id)),
                payload=payload,
            )
            await publisher.publish_team_event(team_id=team_id, event_type=event.event_type, payload=payload)
        except _PUBLISH_ERRORS:
            logger.debug("failed to publish job log event", team_id=str(team_id))

    async def create_job_log(self, data: s.JobLogCreate, publisher: RealtimePublisher | None = None) -> s.JobLog:
        """Insert a single job log entry into the appropriate table."""
        table = self._job_log_table(data)
        row = self._job_log_columns(data)
        returning_cols = [
            "id",
            "job_id",
            "stage",
            "level",
            "message",
            "detail",
            "duration_ms",
            "sequence",
            "created_at",
        ]
        if data.team_id is not None:
            returning_cols.append("team_id")

        log_entry = await self.driver.select_one(
            sql.insert(table).columns(*row.keys()).values(**row).returning(*returning_cols), schema_type=s.JobLog
        )
        if data.team_id is not None and publisher:
            await self._publish_job_log_event(log_entry, data.team_id, publisher)
        return log_entry

    async def create_job_logs(self, entries: list[s.JobLogCreate]) -> int:
        """Batch insert multiple job log entries."""
        if not entries:
            return 0
        for entry in entries:
            table = self._job_log_table(entry)
            row = self._job_log_columns(entry)
            await self.driver.execute(sql.insert(table).columns(*row.keys()).values(**row))
        return len(entries)

    async def get_job_log_summary(self, job_id: UUID) -> s.JobLogSummary:
        """Get an aggregated summary of job log entries by stage."""
        # Note: This requires the get-job-log-summary SQL to be in db/sql/jobs.sql
        from sqlstack.config import db_manager

        stages = await self.driver.select(
            db_manager.get_sql("get-job-log-summary"), job_id=job_id, schema_type=s.JobLogStageSummary
        )
        total_entries = sum(s.entry_count for s in stages)
        total_duration = sum(s.duration_ms or 0 for s in stages) or None
        has_errors = any(s.level == "ERROR" for s in stages)
        has_warnings = any(s.level == "WARNING" for s in stages)
        return s.JobLogSummary(
            job_id=job_id,
            total_entries=total_entries,
            stages=list(stages),
            has_errors=has_errors,
            has_warnings=has_warnings,
            total_duration_ms=total_duration,
        )

    async def _notify_worker(self, event: str, data: str) -> None:
        """Send PostgreSQL NOTIFY to wake up workers."""
        try:
            await self.driver.execute(
                "SELECT pg_notify(:channel, :payload)", channel="sqlstack_tasks", payload=f"{event}:{data}"
            )
        except Exception:  # noqa: BLE001
            await logger.adebug("notification failed", event=event)
