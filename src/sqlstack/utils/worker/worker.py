"""Background worker for processing tasks."""
# ruff: noqa: BLE001

import asyncio
import concurrent.futures
import contextlib
import functools
import inspect
import os
import signal
from collections.abc import Callable, Coroutine
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

from sqlstack.ioc import make_worker_container
from sqlstack.lib.di import Scope, request_container_var, worker_container_var
from sqlstack.lib.exceptions import NonRetryableError
from sqlstack.lib.jobs import get_job_registry
from sqlstack.lib.log import JobLogBuffer, set_buffer
from sqlstack.lib.realtime import RealtimeEntityRef
from sqlstack.lib.settings import get_settings
from sqlstack.utils.otel import create_job_span, end_job_span, get_tracer
from sqlstack.utils.worker.heartbeat import HeartbeatManager

if TYPE_CHECKING:
    from collections.abc import Mapping


logger = structlog.get_logger()

# Type alias for job functions
JobFunction = Callable[..., Coroutine[Any, Any, dict[str, Any] | None]]


async def _safe_alog(method_name: str, event: str, *args: object, **kwargs: object) -> None:
    """Best-effort async logging for shutdown paths where streams may be closed."""
    with contextlib.suppress(ValueError):
        await getattr(logger, method_name)(event, *args, **kwargs)


def _safe_log(method_name: str, event: str, *args: object, **kwargs: object) -> None:
    """Best-effort sync logging for callback/shutdown paths."""
    with contextlib.suppress(ValueError):
        getattr(logger, method_name)(event, *args, **kwargs)


class Worker:
    """Background task worker with 30-second fallback polling."""

    def __init__(
        self,
        *,
        poll_interval: float = 30.0,  # 30-second fallback polling (LISTEN/NOTIFY provides instant wake)
        batch_size: int = 10,
        max_concurrent_jobs: int = 4,
        shutdown_timeout: float = 30.0,
        graceful_shutdown_timeout: float = 5.0,
        register_signals: bool = True,
    ) -> None:
        """Initialize worker.

        Args:
            poll_interval: Seconds between fallback polling for new tasks (default: 30).
                          LISTEN/NOTIFY provides instant wake-up for new tasks.
            batch_size: Maximum tasks to fetch per poll
            max_concurrent_jobs: Maximum number of jobs executing concurrently
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

        # Executors
        self.default_worker_pool = concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count())

        # Database configs for worker operations
        settings = get_settings()

        # Concurrency limit — prefer settings over constructor default
        effective_concurrency = settings.task.MAX_CONCURRENT_JOBS if max_concurrent_jobs == 4 else max_concurrent_jobs
        self._job_semaphore = asyncio.Semaphore(effective_concurrency)
        self._worker_db = settings.db.get_worker_config()
        self._heartbeat_db = settings.db.get_heartbeat_config()

        # Heartbeat Manager - centralized heartbeat for all jobs
        heartbeat_interval = settings.task.HEARTBEAT_INTERVAL
        self._heartbeat_manager = HeartbeatManager(self._heartbeat_db, interval=heartbeat_interval)

        # Stale recovery settings
        self._stale_after_minutes = settings.task.STALE_AFTER_MINUTES

        # Job log capture buffer — accumulates structlog events for persistence
        self._log_buffer = JobLogBuffer()

        # Realtime Channels setup for Worker context
        from litestar.channels.backends.memory import MemoryChannelsBackend

        self._channels_backend = MemoryChannelsBackend(history=settings.channels.HISTORY_TTL)

        # Dependency Injection - pass worker_db so DI uses the same pool
        self.container = make_worker_container(self._worker_db, self._channels_backend)

    async def start(self) -> None:
        """Start the worker."""
        await logger.ainfo("Worker process started", pid=os.getpid())

        # Validate stale recovery invariant: stale_after must be >= 3x heartbeat_interval
        heartbeat_interval_minutes = self._heartbeat_manager.interval / 60.0
        min_stale_after = 3 * heartbeat_interval_minutes
        if self._stale_after_minutes < min_stale_after:
            await logger.awarning(
                "stale_after_minutes is less than 3x heartbeat_interval - healthy jobs may be incorrectly requeued",
                stale_after_minutes=self._stale_after_minutes,
                heartbeat_interval_seconds=self._heartbeat_manager.interval,
                recommended_minimum_minutes=round(min_stale_after, 1),
            )

        # Initialize channels backend
        await self._channels_backend.on_startup()

        # Set the global worker container for worker_scope() access
        worker_container_var.set(self.container)

        # Activate the job log capture buffer so the structlog processor starts capturing
        set_buffer(self._log_buffer)

        # Start the heartbeat manager
        await self._heartbeat_manager.start()

        # Log available jobs
        scheduled_count = sum(1 for job in self.job_registry.values() if hasattr(job, "__schedule_config__"))
        ad_hoc_count = len(self.job_registry) - scheduled_count
        await logger.adebug(
            "Worker job registry loaded",
            total_jobs=len(self.job_registry),
            scheduled_jobs=scheduled_count,
            adhoc_jobs=ad_hoc_count,
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
            try:
                async with self.container(scope=Scope.REQUEST) as request_container:
                    from sqlstack.domain.system.services import TaskService

                    task_service = await request_container.get(TaskService)
                    await task_service.requeue_stale_running()
            except Exception as e:
                await logger.aerror("Failed initial stale task recovery", error=str(e))

            # Run main worker loop
            await self._run()
        except asyncio.CancelledError:
            await _safe_alog("ainfo", "Worker cancelled")
        finally:
            await self._cleanup()

    def _handle_shutdown(self) -> None:
        """Handle shutdown signal."""
        _safe_log("info", "Shutdown signal received")
        self.shutdown_event.set()

    async def _run(self) -> None:
        """Main worker loop."""
        while not self.shutdown_event.is_set():
            try:
                # Fetch and process pending tasks
                await self._process_pending_tasks()

                # Requeue stale running tasks periodically (once a minute)
                now = asyncio.get_event_loop().time()
                if now - self._last_requeue_check > 60:
                    async with self.container(scope=Scope.REQUEST) as request_container:
                        from sqlstack.domain.system.services import TaskService

                        task_service = await request_container.get(TaskService)
                        await task_service.requeue_stale_running(
                            stale_after=timedelta(minutes=self._stale_after_minutes)
                        )
                    self._last_requeue_check = now

                # Clean up completed tasks
                self._cleanup_completed_tasks()

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
                await logger.aexception("Error in worker loop")
                await asyncio.sleep(self.poll_interval)

    async def _listen_for_notifications(self) -> None:
        """Listen on PostgreSQL channel to wake the worker without polling."""

        async def _do_listen() -> None:
            async with self._worker_db.provide_session() as driver:

                def listener(*_: object) -> None:
                    self._notification_event.set()

                await driver.connection.add_listener("sqlstack_tasks", listener)

                try:
                    while not self.shutdown_event.is_set():
                        try:
                            await asyncio.wait_for(self.shutdown_event.wait(), timeout=1)
                        except TimeoutError:
                            continue
                finally:
                    with contextlib.suppress(Exception):
                        await driver.connection.remove_listener("sqlstack_tasks", listener)

        while not self.shutdown_event.is_set():
            try:
                await _do_listen()
            except Exception:
                await logger.awarning("Notification listener error; retrying", exc_info=True)
                await asyncio.sleep(1)

    async def _process_pending_tasks(self) -> None:
        """Fetch and process pending tasks."""
        from sqlstack.domain.system.services import TaskService

        async with self.container(scope=Scope.REQUEST) as request_container:
            task_service = await request_container.get(TaskService)
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
                    task.add_done_callback(self._consume_task_exception)
                    self.running_tasks[str(task_id)] = task

    def _consume_task_exception(self, task: asyncio.Task[None]) -> None:
        """Ensure task exceptions are observed to avoid leaking into the event loop."""
        with contextlib.suppress(asyncio.CancelledError):
            try:
                task.result()
            except NonRetryableError:
                pass
            except Exception as exc:
                _safe_log("exception", "Worker task failed", exc_info=exc)

    async def _execute_task(self, task_data: Any) -> None:
        """Execute a single task with concurrency limiting.

        Args:
            task_data: Task information from database
        """
        async with self._job_semaphore:
            await self._execute_task_inner(task_data)

    async def _execute_task_inner(self, task_data: Any) -> None:
        """Execute a single task."""
        from sqlstack.domain.system.services import TaskService

        task_id = task_data.id
        function_name = task_data.function
        raw_data = task_data.data or {}
        data = {k: v for k, v in raw_data.items() if not k.startswith("_")}

        # Bind job context to all logs within this task execution
        clear_contextvars()
        ctx_extras: dict[str, str] = {}
        if raw_data.get("team_id"):
            ctx_extras["team_id"] = str(raw_data["team_id"])
        bind_contextvars(job_id=str(task_id), job_function=function_name, **ctx_extras)

        await logger.ainfo("Executing job")

        def _raise_unknown_function() -> None:
            msg = f"Unknown function: {function_name}"
            raise ValueError(msg)

        tracer = get_tracer()
        span = create_job_span(tracer, job_id=str(task_id), function_name=function_name, data=data)
        error: BaseException | None = None

        func = self.job_registry.get(function_name)
        timeout = getattr(func, "_timeout", 300) if func else 300

        try:
            if func is None:
                _raise_unknown_function()
                return

            async with self.container(scope=Scope.REQUEST) as request_container:
                token = request_container_var.set(request_container)
                try:
                    from sqlstack.lib.realtime import RealtimePublisher

                    publisher = await request_container.get(RealtimePublisher)

                    # Register job for heartbeat updates
                    self._heartbeat_manager.register_job(task_id)

                    # Publish status update
                    await self._publish_status(publisher, task_id, "started", raw_data)

                    # Execute the function
                    result = await self._run_job_function(
                        request_container=request_container, func=func, task_id=task_id, data=data, job_timeout=timeout
                    )

                    # Mark as completed
                    task_service = await request_container.get(TaskService)
                    await task_service.complete_task(task_id, result={"result": result} if result else None)

                    # Publish final status
                    await self._publish_status(publisher, task_id, "completed", raw_data, result=result)

                finally:
                    request_container_var.reset(token)

            await logger.ainfo("Job completed")

        except Exception as e:
            error = e
            fail_task = asyncio.create_task(self._job_failed(task_id, function_name, raw_data, e))
            await fail_task

        except asyncio.CancelledError as e:
            error = e
            await self._job_cancelled(task_id)
            raise

        finally:
            end_job_span(span, error=error)

            self._heartbeat_manager.unregister_job(task_id)

            flush_task = asyncio.create_task(self._flush_job_logs(task_id))
            await flush_task

            self.running_tasks.pop(str(task_id), None)
            clear_contextvars()

    async def _publish_status(
        self,
        publisher: "RealtimePublisher",
        task_id: UUID,
        status: str,
        raw_data: dict[str, Any],
        *,
        result: Any = None,
        error: str | None = None,
    ) -> None:
        """Publish task status update to realtime channels."""
        event_type = f"task.status.{status}"
        payload = {"task_id": str(task_id), "status": status}
        if result:
            payload["result"] = result
        if error:
            payload["error"] = error

        team_id = raw_data.get("team_id")
        user_id = raw_data.get("user_id")

        if team_id:
            await publisher.publish_team_event(
                team_id=UUID(str(team_id)),
                event_type=event_type,
                payload=payload,
                entity=RealtimeEntityRef(type="task", id=str(task_id)),
                user_id=UUID(str(user_id)) if user_id else None,
            )
        elif user_id:
            await publisher.publish_user_event(
                user_id=UUID(str(user_id)),
                event_type=event_type,
                payload=payload,
                entity=RealtimeEntityRef(type="task", id=str(task_id)),
            )
        else:
            await publisher.publish_global_event(
                event_type=event_type, payload=payload, entity=RealtimeEntityRef(type="task", id=str(task_id))
            )

    async def _flush_job_logs(self, task_id: UUID) -> None:
        """Flush buffered job log entries to PostgreSQL."""
        from sqlstack.domain.system.services import TaskService

        try:
            async with self.container(scope=Scope.REQUEST) as flush_container:
                flush_service = await flush_container.get(TaskService)
                await self._log_buffer.flush(flush_service)
        except Exception:
            await logger.awarning("Failed to flush job log buffer after task execution", job_id=str(task_id))
        self._log_buffer.reset_sequences(str(task_id))

    async def _run_job_function(
        self, *, request_container: Any, func: JobFunction, task_id: UUID, data: dict[str, Any], job_timeout: int
    ) -> Any:
        """Execute the job function with timeout enforcement."""
        try:
            original_func = getattr(func, "__wrapped__", func)
            if not inspect.iscoroutinefunction(original_func):
                loop = asyncio.get_running_loop()
                p = functools.partial(original_func, **data)
                return await asyncio.wait_for(loop.run_in_executor(self.default_worker_pool, p), timeout=job_timeout)

            task_kwargs = dict(data)
            if "_job_id" not in task_kwargs:
                sig = inspect.signature(func)
                has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
                if has_var_keyword or "_job_id" in sig.parameters:
                    task_kwargs["_job_id"] = str(task_id)
            return await asyncio.wait_for(func(**task_kwargs), timeout=job_timeout)

        except TimeoutError:
            await logger.awarning("Job timed out", timeout=job_timeout)
            from sqlstack.domain.system.services import TaskService

            task_service = await request_container.get(TaskService)
            await task_service.fail_task(task_id, error=f"Task timed out after {job_timeout}s", retry=True)
            raise

    async def _job_failed(self, task_id: UUID, function_name: str, raw_data: dict[str, Any], e: Exception) -> None:
        """Handle job failure."""
        from sqlstack.domain.system.services import TaskService

        if isinstance(e, NonRetryableError):
            await logger.awarning("Job failed", error=str(e))
        else:
            await logger.aexception("Job failed")

        retry_allowed = not isinstance(e, NonRetryableError)

        async with self.container(scope=Scope.REQUEST) as request_container:
            token = request_container_var.set(request_container)
            try:
                task_service = await request_container.get(TaskService)
                await task_service.fail_task(task_id, error=str(e), retry=retry_allowed)

                from sqlstack.lib.realtime import RealtimePublisher

                publisher = await request_container.get(RealtimePublisher)
                await self._publish_status(publisher, task_id, "failed", raw_data, error=str(e))
            finally:
                request_container_var.reset(token)

    async def _job_cancelled(self, task_id: UUID) -> None:
        """Handle job cancellation during shutdown."""
        from sqlstack.domain.system.services import TaskService

        await logger.awarning("Job cancelled during shutdown")
        async with self.container(scope=Scope.REQUEST) as request_container:
            token = request_container_var.set(request_container)
            try:
                task_service = await request_container.get(TaskService)
                await task_service.fail_task(task_id, error="Task cancelled during shutdown", retry=True)
            finally:
                request_container_var.reset(token)

    def _cleanup_completed_tasks(self) -> None:
        """Remove completed tasks from tracking."""
        completed = [task_id for task_id, task in self.running_tasks.items() if task.done()]

        for task_id in completed:
            self.running_tasks.pop(task_id, None)

    async def _cleanup(self) -> None:
        """Clean up on shutdown."""
        await _safe_alog("ainfo", "Worker shutting down")

        if self._listener_task is not None:
            self.shutdown_event.set()
            try:
                await asyncio.wait_for(self._listener_task, timeout=2.0)
            except TimeoutError:
                self._listener_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._listener_task
            self._listener_task = None

        if self._heartbeat_manager:
            await self._heartbeat_manager.stop(shutdown_timeout=2.0)

        running = list(self.running_tasks.values())
        if running:
            await _safe_alog("ainfo", "Allowing running tasks to finish", task_count=len(running))
            try:
                await asyncio.wait_for(
                    asyncio.gather(*running, return_exceptions=True), timeout=self.graceful_shutdown_timeout
                )
            except TimeoutError:
                await _safe_alog("awarning", "Graceful shutdown timed out; cancelling running tasks")

        still_running = [t for t in self.running_tasks.values() if not t.done()]
        for task in still_running:
            task.cancel()

        if still_running:
            await _safe_alog("ainfo", "Waiting for cancelled tasks to finish", task_count=len(still_running))
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    asyncio.gather(*still_running, return_exceptions=True), timeout=self.shutdown_timeout
                )

        try:
            from sqlstack.domain.system.services import TaskService

            async with self.container(scope=Scope.REQUEST) as flush_container:
                flush_service = await flush_container.get(TaskService)
                await self._log_buffer.flush(flush_service)
        except Exception:
            await _safe_alog("awarning", "Failed final log buffer flush during shutdown")
        set_buffer(None)

        await self._channels_backend.on_shutdown()

        self.default_worker_pool.shutdown(wait=True)
        await self.container.close()
        await _safe_alog("ainfo", "Worker shutdown complete")
