"""Litestar plugin for worker system integration."""

from __future__ import annotations

import asyncio
import contextlib
import random
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from litestar.plugins import InitPluginProtocol

from sqlstack.lib.jobs import discover_jobs, get_scheduled_jobs, load_jobs

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.config.app import AppConfig

logger = structlog.get_logger()


class WorkerPlugin(InitPluginProtocol):
    """Litestar plugin for background worker system.

    This plugin:
    - Discovers and loads job modules on app startup
    - Initializes scheduled jobs
    - Optionally starts worker process alongside server
    - TaskService is provided via Dishka dependency injection
    """

    def __init__(
        self, *, start_worker: bool = False, job_packages: list[str] | None = None, auto_discover: bool = True
    ) -> None:
        """Initialize the worker plugin.

        Args:
            start_worker: Whether to start worker process with server
            job_packages: List of Python packages to search for jobs
            auto_discover: Whether to auto-discover job modules
        """
        self.start_worker = start_worker
        self.job_packages = job_packages or ["sqlstack.server.jobs"]
        self.auto_discover = auto_discover
        self._worker_task: asyncio.Task[None] | None = None

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        """Initialize the plugin when app is created.

        Args:
            app_config: The Litestar app configuration

        Returns:
            Updated app configuration
        """
        # Add startup/shutdown handlers
        if not app_config.on_startup:
            app_config.on_startup = []
        if not app_config.on_shutdown:
            app_config.on_shutdown = []

        app_config.on_startup.append(self._on_startup)
        app_config.on_shutdown.append(self._on_shutdown)

        return app_config

    async def _on_startup(self, app: Litestar) -> None:
        """Handle app startup.

        Args:
            app: The Litestar application instance
        """
        if self.auto_discover:
            # Discover and load job modules
            for package in self.job_packages:
                discover_jobs(package)

            # Load jobs into registry
            load_jobs()

        # Initialize scheduled jobs
        await self._initialize_schedules()

        # Optionally start worker process
        if self.start_worker:
            await self._start_worker()

    async def _on_shutdown(self, app: Litestar) -> None:
        """Handle app shutdown.

        Args:
            app: The Litestar application instance
        """
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task

    async def _initialize_schedules(self) -> None:
        """Initialize scheduled jobs in the database."""
        from sqlspec import sql

        from sqlstack.config import db, db_manager
        from sqlstack.domain.system.services import TaskService

        scheduled_jobs = get_scheduled_jobs()
        if not scheduled_jobs:
            return

        async with db_manager.provide_session(db) as driver:
            task_service = TaskService(driver=driver)

            # Get existing scheduled tasks from database
            existing_schedules = await driver.select(
                sql.select("key", "data", "id", "scheduled_at")
                .from_("job")
                .where("key LIKE 'scheduled-%'")
                .where("status IN ('pending', 'scheduled')")
            )

            # Create a map of existing schedules by job name
            existing_map: dict[str, Any] = {}
            for schedule in existing_schedules:
                job_name = schedule["key"].replace("scheduled-", "")
                existing_map[job_name] = schedule

            # Process all currently defined schedules in code
            for job_name, config in scheduled_jobs.items():
                existing = existing_map.get(job_name)

                if existing:
                    # Compare the schedule configuration
                    stored_config: dict[str, Any] = existing["data"].get("_schedule_config", {})

                    # Check if schedule has changed
                    schedule_changed = (
                        stored_config.get("cron") != config.cron
                        or stored_config.get("interval") != config.interval
                        or stored_config.get("timezone") != config.timezone
                    )

                    if schedule_changed:
                        # Cancel the old scheduled task
                        await driver.execute(
                            sql.update("job")
                            .set(status="cancelled", completed_at=datetime.now(UTC))
                            .where_eq("id", existing["id"])
                        )

                        # Calculate new run time based on updated schedule
                        now = datetime.now(UTC)
                        next_run = config.get_next_run(after=now)

                        # Add jitter if configured
                        if config.jitter:
                            jitter_seconds = random.randint(0, config.jitter)  # noqa: S311
                            next_run += timedelta(seconds=jitter_seconds)

                        # Create new scheduled task with updated configuration
                        await task_service.create_task(
                            function=job_name,
                            data={"_scheduled": True, "_schedule_config": config.__dict__},
                            scheduled_at=next_run,
                            key=f"scheduled-{job_name}",
                            priority=5,
                        )
                else:
                    # New scheduled job, create it
                    now = datetime.now(UTC)

                    if config.initial_delay:
                        first_run = now + timedelta(seconds=config.initial_delay)
                    else:
                        first_run = config.get_next_run(after=now)

                    # Add jitter if configured
                    if config.jitter:
                        jitter_seconds = random.randint(0, config.jitter)  # noqa: S311
                        first_run += timedelta(seconds=jitter_seconds)

                    # Create scheduled task
                    await task_service.create_task(
                        function=job_name,
                        data={"_scheduled": True, "_schedule_config": config.__dict__},
                        scheduled_at=first_run,
                        key=f"scheduled-{job_name}",
                        priority=5,
                    )

    async def _start_worker(self) -> None:
        """Start the worker process in background."""
        try:
            from sqlstack.lib.worker import Worker

            async def run_worker() -> None:
                worker = Worker()
                await worker.start()

            self._worker_task = asyncio.create_task(run_worker())

            await logger.ainfo("started background worker task")

        except (ImportError, AttributeError, RuntimeError) as e:
            await logger.aerror("failed to start background worker", error=str(e))
