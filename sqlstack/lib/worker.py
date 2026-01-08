"""Background worker for processing tasks."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
from collections.abc import Callable, Coroutine
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import structlog

from sqlstack.domain.system.services import TaskService
from sqlstack.lib.exceptions import NonRetryableError
from sqlstack.lib.jobs import get_job_registry

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from sqlspec.adapters.asyncpg import AsyncpgConfig, AsyncpgDriver


logger = structlog.get_logger()

# Type alias for job functions
JobFunction = Callable[..., Coroutine[Any, Any, dict[str, Any] | None]]

# Interval for requeue check (seconds)
REQUEUE_CHECK_INTERVAL = 60


class Worker:
    """Background task worker with 3-second polling and LISTEN/NOTIFY support."""

    # Optional attributes for dependency injection (used in testing)
    task_service: TaskService | None
    db_config: AsyncpgConfig | None

    def __init__(
        self,
        *,
        poll_interval: float = 3.0,  # 3-second polling as default
        batch_size: int = 10,
        shutdown_timeout: float = 30.0,
        graceful_shutdown_timeout: float = 5.0,
        register_signals: bool = True,
    ) -> None:
        """Initialize worker.

        Args:
            poll_interval: Seconds between polling for new tasks (default: 3)
            batch_size: Maximum tasks to fetch per poll
            shutdown_timeout: Maximum time to wait for tasks to complete on shutdown
            graceful_shutdown_timeout: Time to wait for tasks to finish before we cancel them on shutdown
            register_signals: Whether to install SIGINT/SIGTERM handlers (disable in tests)
        """
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.shutdown_timeout = shutdown_timeout
        self.graceful_shutdown_timeout = graceful_shutdown_timeout
        self.register_signals = register_signals

        self.running_tasks: dict[str, asyncio.Task[None]] = {}
        self.shutdown_event: asyncio.Event = asyncio.Event()
        self.job_registry: Mapping[str, JobFunction] = get_job_registry()
        self._notification_event = asyncio.Event()
        self._listener_task: asyncio.Task[None] | None = None
        self._last_requeue_check: float = 0.0

        # DI attributes - can be set externally for testing
        self.task_service = None
        self.db_config = None

    @asynccontextmanager
    async def _get_session(self) -> AsyncGenerator[AsyncpgDriver, None]:
        """Get a database session, using injected config if available."""
        if self.db_config is not None:
            async with self.db_config.provide_session() as driver:
                yield driver
        else:
            from sqlstack.config import db, db_manager

            async with db_manager.provide_session(db) as driver:
                yield driver

    def _get_task_service(self, driver: AsyncpgDriver) -> TaskService:
        """Get a TaskService, using injected service if available."""
        if self.task_service is not None:
            return self.task_service

        return TaskService(driver=driver)

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

        # Register signal handlers
        if self.register_signals:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                with contextlib.suppress(NotImplementedError):
                    loop.add_signal_handler(sig, self._handle_shutdown)

        # Start LISTEN/NOTIFY listener (best-effort)
        self._listener_task = asyncio.create_task(self._listen_for_notifications())

        try:
            # Requeue any stale running tasks left from crashes
            async with self._get_session() as driver:
                task_service = self._get_task_service(driver)
                await task_service.requeue_stale_running()

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

                # Requeue stale running tasks periodically (once a minute)
                now = asyncio.get_event_loop().time()
                if now - self._last_requeue_check > REQUEUE_CHECK_INTERVAL:
                    async with self._get_session() as driver:
                        task_service = self._get_task_service(driver)
                        await task_service.requeue_stale_running(stale_after=timedelta(minutes=1))
                    self._last_requeue_check = now

                # Clean up completed tasks
                self._cleanup_completed_tasks()

                # Wait for either shutdown, notification, or poll timeout
                wait_tasks: list[asyncio.Task[bool]] = [
                    asyncio.create_task(self.shutdown_event.wait()),
                    asyncio.create_task(self._notification_event.wait()),
                ]
                _done, pending = await asyncio.wait(
                    wait_tasks, timeout=self.poll_interval, return_when=asyncio.FIRST_COMPLETED
                )
                for p in pending:
                    p.cancel()
                if self._notification_event.is_set():
                    self._notification_event.clear()

            except (ConnectionError, OSError, RuntimeError):
                await logger.aexception("error in worker loop")
                await asyncio.sleep(self.poll_interval)

    async def _listen_for_notifications(self) -> None:
        """Listen on PostgreSQL channel to wake the worker without polling."""

        async def _do_listen() -> None:
            async with self._get_session() as driver:

                def listener(*_: object) -> None:
                    self._notification_event.set()

                await driver.connection.add_listener("sqlstack_tasks", listener)
                await driver.execute("LISTEN sqlstack_tasks")

                try:
                    while not self.shutdown_event.is_set():
                        try:
                            await asyncio.wait_for(self.shutdown_event.wait(), timeout=1)
                        except TimeoutError:
                            continue
                finally:
                    with contextlib.suppress(Exception):
                        await driver.execute("UNLISTEN sqlstack_tasks")
                    with contextlib.suppress(Exception):
                        await driver.connection.remove_listener("sqlstack_tasks", listener)

        while not self.shutdown_event.is_set():
            try:
                await _do_listen()
            except Exception:  # noqa: BLE001
                await logger.awarning("notification listener error; retrying", exc_info=True)
                await asyncio.sleep(1)

    async def _heartbeat_loop(self, task_id: Any) -> None:
        """Periodically update heartbeat for a running task."""
        while not self.shutdown_event.is_set():
            try:
                await asyncio.wait_for(self.shutdown_event.wait(), timeout=60)
                # shutdown_event set; break
                break
            except TimeoutError:
                async with self._get_session() as driver:
                    task_service = self._get_task_service(driver)
                    await task_service.touch_heartbeat(task_id)

    async def _process_pending_tasks(self) -> None:
        """Fetch and process pending tasks."""
        # Get fresh connection for this operation
        async with self._get_session() as driver:
            task_service = self._get_task_service(driver)
            tasks = await task_service.get_pending_tasks(limit=self.batch_size)

            for task_data in tasks:
                task_id = task_data.id

                # Skip if already running
                if str(task_id) in self.running_tasks:
                    continue

                # Try to claim the task
                if await task_service.claim_task(task_id):
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

        heartbeat_task: asyncio.Task[None] | None = None

        try:
            # Get function from registry
            func = self.job_registry.get(function_name)
            if func is None:
                _raise_unknown_function()
                return  # This should never be reached due to the exception above

            heartbeat_task = asyncio.create_task(self._heartbeat_loop(task_id))

            # Execute the function
            result = await func(**data)

            # Mark as completed with fresh connection
            async with self._get_session() as driver:
                task_service = self._get_task_service(driver)
                await task_service.complete_task(task_id, result={"result": result} if result else None)

            await logger.ainfo("task completed successfully", task_id=str(task_id), function=function_name)

        except (ValueError, TypeError, ImportError, AttributeError, RuntimeError) as e:
            await logger.aexception("task execution failed", task_id=str(task_id), function=function_name)

            # Decide whether to retry based on non-retryable marker
            retry_allowed = not isinstance(e, NonRetryableError)

            # Mark as failed with fresh connection
            async with self._get_session() as driver:
                task_service = self._get_task_service(driver)
                await task_service.fail_task(task_id, error=str(e), retry=retry_allowed)

        except asyncio.CancelledError:
            # Shutdown initiated; mark the task as retryable and re-raise to propagate cancellation
            await logger.awarning("task cancelled during shutdown", task_id=str(task_id), function=function_name)
            async with self._get_session() as driver:
                task_service = self._get_task_service(driver)
                await task_service.fail_task(task_id, error="Task cancelled during shutdown", retry=True)
            raise

        finally:
            # Cancel heartbeat task first
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat_task

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

        # Stop the listener task
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task

        # First, give running tasks a grace period to finish naturally
        running = list(self.running_tasks.values())
        if running:
            await logger.ainfo("allowing running tasks to finish", task_count=len(running))
            try:
                await asyncio.wait_for(
                    asyncio.gather(*running, return_exceptions=True), timeout=self.graceful_shutdown_timeout
                )
            except TimeoutError:
                await logger.awarning("graceful shutdown timed out; cancelling running tasks")

        # Cancel any tasks still running after grace period
        still_running = [t for t in self.running_tasks.values() if not t.done()]
        for task in still_running:
            task.cancel()

        if still_running:
            await logger.ainfo("waiting for cancelled tasks to finish", task_count=len(still_running))
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    asyncio.gather(*still_running, return_exceptions=True), timeout=self.shutdown_timeout
                )

        await logger.ainfo("worker shutdown complete")
