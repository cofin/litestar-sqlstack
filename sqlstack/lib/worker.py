"""Background worker for processing tasks."""

from __future__ import annotations

import asyncio
import os
import signal
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

import structlog

from sqlstack.config import db_config, sqlspec
from sqlstack.lib.jobs import get_job_registry

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sqlstack.services import TaskService

logger = structlog.get_logger()

# Type alias for job functions
JobFunction = Callable[..., Coroutine[Any, Any, dict[str, Any] | None]]


class Worker:
    """Background task worker with 3-second polling."""

    def __init__(
        self,
        *,
        poll_interval: float = 3.0,  # 3-second polling as requested
        batch_size: int = 10,
        shutdown_timeout: float = 30.0,
    ) -> None:
        """Initialize worker.

        Args:
            poll_interval: Seconds between polling for new tasks (default: 3)
            batch_size: Maximum tasks to fetch per poll
            shutdown_timeout: Maximum time to wait for tasks to complete on shutdown
        """
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.shutdown_timeout = shutdown_timeout

        self.running_tasks: dict[str, asyncio.Task[None]] = {}
        self.shutdown_event: asyncio.Event = asyncio.Event()
        self.job_registry: Mapping[str, JobFunction] = get_job_registry()
        self.task_service: TaskService | None = None

    async def start(self) -> None:
        """Start the worker."""
        await logger.ainfo("worker starting", pid=os.getpid())

        # Log available jobs
        scheduled_count = sum(1 for job in self.job_registry.values() if hasattr(job, "__schedule_config__"))
        ad_hoc_count = len(self.job_registry) - scheduled_count
        await logger.ainfo(
            "worker initialized with job functions",
            total_jobs=len(self.job_registry),
            scheduled=scheduled_count,
            ad_hoc=ad_hoc_count,
        )

        # Get database config
        db = sqlspec.get_config(db_config)

        # Initialize database and service
        async with sqlspec.provide_session(db) as driver:
            from sqlstack.services import TaskService

            self.task_service = TaskService(driver=driver)

            # Register signal handlers
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, self._handle_shutdown)

            try:
                # Run main worker loop
                await self._run()
            except asyncio.CancelledError:
                await logger.ainfo("worker cancelled")
            finally:
                await self._cleanup()

    def _handle_shutdown(self) -> None:
        """Handle shutdown signal."""
        logger.info("shutdown signal received")
        self.shutdown_event.set()

    async def _run(self) -> None:
        """Main worker loop."""
        while not self.shutdown_event.is_set():
            try:
                # Fetch and process pending tasks
                await self._process_pending_tasks()

                # Clean up completed tasks
                self._cleanup_completed_tasks()

                # Wait before next poll
                try:
                    await asyncio.wait_for(self.shutdown_event.wait(), timeout=self.poll_interval)
                except TimeoutError:
                    # Normal timeout, continue loop
                    continue

            except (ConnectionError, OSError, RuntimeError):
                await logger.aexception("error in worker loop")
                await asyncio.sleep(self.poll_interval)

    async def _process_pending_tasks(self) -> None:
        """Fetch and process pending tasks."""
        if not self.task_service:
            return

        tasks = await self.task_service.get_pending_tasks(limit=self.batch_size)

        for task_data in tasks:
            task_id = task_data.id

            # Skip if already running
            if str(task_id) in self.running_tasks:
                continue

            # Try to claim the task
            if await self.task_service.claim_task(task_id):
                # Start processing in background
                task = asyncio.create_task(self._execute_task(task_data))
                self.running_tasks[str(task_id)] = task

    async def _execute_task(self, task_data: Any) -> None:
        """Execute a single task.

        Args:
            task_data: Task information from database
        """
        task_id = task_data.id
        function_name = task_data.function
        data: dict[str, Any] = task_data.data or {}

        await logger.ainfo("executing task", task_id=str(task_id), function=function_name)

        def _raise_unknown_function() -> None:
            msg = f"unknown function: {function_name}"
            raise ValueError(msg)

        try:
            # Get function from registry
            func = self.job_registry.get(function_name)
            if func is None:
                _raise_unknown_function()
                return  # This should never be reached due to the exception above

            # Execute the function
            result = await func(**data)

            # Mark as completed
            if self.task_service:
                await self.task_service.complete_task(task_id, result={"result": result} if result else None)

            await logger.ainfo("task completed successfully", task_id=str(task_id), function=function_name)

        except (ValueError, TypeError, ImportError, AttributeError, RuntimeError) as e:
            await logger.aexception("task execution failed", task_id=str(task_id), function=function_name)

            # Mark as failed
            if self.task_service:
                await self.task_service.fail_task(task_id, error=str(e), retry=True)

        finally:
            # Remove from running tasks
            self.running_tasks.pop(str(task_id), None)

    def _cleanup_completed_tasks(self) -> None:
        """Remove completed tasks from tracking."""
        completed = [task_id for task_id, task in self.running_tasks.items() if task.done()]

        for task_id in completed:
            self.running_tasks.pop(task_id, None)

    async def _cleanup(self) -> None:
        """Clean up on shutdown."""
        await logger.ainfo("worker shutting down")

        # Cancel all running tasks
        for task in self.running_tasks.values():
            task.cancel()

        # Wait for tasks to complete
        if self.running_tasks:
            await logger.ainfo("waiting for tasks to complete", count=len(self.running_tasks))

            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.running_tasks.values(), return_exceptions=True), timeout=self.shutdown_timeout
                )
            except TimeoutError:
                await logger.awarning("some tasks did not complete in time")

        await logger.ainfo("worker shutdown complete")
