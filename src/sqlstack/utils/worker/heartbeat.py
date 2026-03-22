"""Heartbeat manager for background worker jobs.

Manages heartbeat updates for all active jobs in an asyncio background task.
"""
# ruff: noqa: BLE001

import asyncio
import contextlib
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

if TYPE_CHECKING:
    from sqlspec.adapters.asyncpg import AsyncpgConfig

logger = structlog.get_logger()

# Failure thresholds for escalation
_FAILURE_ERROR_THRESHOLD = 3
_FAILURE_DEGRADED_THRESHOLD = 5

# Event loop latency threshold (seconds)
_EVENT_LOOP_LATENCY_WARN = 1.0


def _safe_log(method_name: str, event: str, *args: object, **kwargs: object) -> None:
    """Best-effort logging for shutdown paths where streams may already be closed."""
    with contextlib.suppress(ValueError):
        getattr(logger, method_name)(event, *args, **kwargs)


class HeartbeatManager:
    """Manages heartbeat updates for all active jobs.

    Uses AsyncpgConfig to manage the connection pool. Jobs register when
    they start and unregister when they complete. The manager batch-updates
    all active job heartbeats every interval.

    Failure escalation:
    - After 3 consecutive failures, logs at ERROR level.
    - After 5 consecutive failures, sets a ``degraded`` flag observable
      by the worker for health checks.
    - Counter resets on any successful update.

    Usage:
        manager = HeartbeatManager(heartbeat_config)
        await manager.start()

        # When job starts
        manager.register_job(job_id)

        # When job completes
        manager.unregister_job(job_id)

        # On shutdown
        await manager.stop()
    """

    def __init__(self, config: "AsyncpgConfig", *, interval: float = 30.0) -> None:
        """Initialize the heartbeat manager.

        Args:
            config: AsyncpgConfig for database connections.
            interval: Seconds between heartbeat updates.
        """
        self._config = config
        self._interval = interval

        self._active_jobs: set[UUID] = set()
        self._task: asyncio.Task[None] | None = None
        self._consecutive_failures: int = 0
        self.degraded: bool = False

    @property
    def interval(self) -> float:
        """Return the heartbeat interval in seconds."""
        return self._interval

    def register_job(self, job_id: UUID) -> None:
        """Register a job to receive heartbeat updates."""
        self._active_jobs.add(job_id)

    def unregister_job(self, job_id: UUID) -> None:
        """Unregister a job from heartbeat updates."""
        self._active_jobs.discard(job_id)

    async def start(self) -> None:
        """Start the heartbeat manager task."""
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run())
        _safe_log("debug", "Heartbeat manager started", interval=self._interval)

    async def stop(self, shutdown_timeout: float = 10.0) -> None:
        """Stop the heartbeat manager task."""
        if not self._task or self._task.done():
            return

        self._task.cancel()
        try:
            async with asyncio.timeout(shutdown_timeout):
                await self._task
        except (asyncio.CancelledError, TimeoutError):
            pass
        except Exception:
            _safe_log("exception", "Error stopping heartbeat manager")
        finally:
            self._task = None
            _safe_log("debug", "Heartbeat manager stopped")

    async def _run(self) -> None:
        """Async heartbeat loop with event loop health monitoring."""
        _safe_log("debug", "Heartbeat loop started")

        try:
            while True:
                await asyncio.sleep(self._interval)

                # Event loop health check: measure actual latency of a no-op await
                before = time.monotonic()
                await asyncio.sleep(0)
                latency = time.monotonic() - before
                if latency > _EVENT_LOOP_LATENCY_WARN:
                    logger.warning(
                        "Event loop latency exceeded threshold",
                        latency_seconds=round(latency, 3),
                        threshold=_EVENT_LOOP_LATENCY_WARN,
                    )

                job_ids = list(self._active_jobs)

                if job_ids:
                    await self._update_heartbeats(job_ids)
        except asyncio.CancelledError:
            _safe_log("debug", "Heartbeat loop cancelled")
            raise
        except Exception:
            _safe_log("exception", "Heartbeat manager crashed")
        finally:
            _safe_log("debug", "Heartbeat loop stopped")

    async def _update_heartbeats(self, job_ids: list[UUID]) -> None:
        """Batch update heartbeats for all active jobs."""
        try:
            async with self._config.provide_session() as driver:
                result = await driver.execute(
                    """
                    UPDATE job
                    SET heartbeat_at = $1
                    WHERE id = ANY($2) AND status = 'running'
                    """,
                    datetime.now(UTC),
                    job_ids,
                )
                if result.rows_affected > 0:
                    logger.debug("Updated heartbeats", count=result.rows_affected, total_jobs=len(job_ids))

            # Success — reset failure state
            if self._consecutive_failures > 0:
                logger.info("Heartbeat recovered after %d consecutive failures", self._consecutive_failures)
            self._consecutive_failures = 0
            self.degraded = False

        except Exception:
            self._consecutive_failures += 1

            if self._consecutive_failures >= _FAILURE_DEGRADED_THRESHOLD:
                self.degraded = True
                logger.exception(
                    "Heartbeat degraded — %d consecutive failures", self._consecutive_failures, job_count=len(job_ids)
                )
            elif self._consecutive_failures >= _FAILURE_ERROR_THRESHOLD:
                logger.exception(
                    "Heartbeat failing repeatedly — %d consecutive failures",
                    self._consecutive_failures,
                    job_count=len(job_ids),
                )
            else:
                logger.exception("Failed to update heartbeats", job_count=len(job_ids))
