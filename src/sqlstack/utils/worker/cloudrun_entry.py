"""Cloud Run Jobs worker entry point with local worker parity.

This module provides the entry point for Cloud Run container execution.
It maintains behavioral parity with the local worker:
- Heartbeat loop during execution
- NonRetryableError handling for retry decisions
- Loads kwargs from database (env var is fallback only)
"""

# ruff: noqa: BLE001
import asyncio
import contextlib
import os
import sys
from uuid import UUID

import structlog

from sqlstack.lib.exceptions import NonRetryableError

logger = structlog.get_logger()


async def _heartbeat_loop(task_id: UUID, shutdown_event: asyncio.Event) -> None:
    """Periodically update heartbeat for a running task (parity with local worker).

    Args:
        task_id: Job ID to update heartbeat for
        shutdown_event: Event to signal shutdown
    """
    from sqlstack.config import db, db_manager
    from sqlstack.domain.system.services import TaskService

    while not shutdown_event.is_set():
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=30)
            break
        except TimeoutError:
            try:
                async with db_manager.provide_session(db) as driver:
                    task_service = TaskService(driver=driver)
                    await task_service.touch_heartbeat(task_id)
            except Exception:
                await logger.aexception("failed to update heartbeat", job_id=str(task_id))


async def execute_cloudrun_job() -> int:  # noqa: PLR0911
    """Execute a single job from Cloud Run environment.

    Behavioral parity with local worker:
    - Heartbeat loop during execution
    - NonRetryableError check for retry decisions
    - Kwargs loaded from database (authoritative source)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    from sqlstack.config import db, db_manager
    from sqlstack.domain.system.services import TaskService
    from sqlstack.lib.jobs import get_job_registry, load_jobs

    # Read job ID from environment (required)
    job_id_str = os.environ.get("SQLSTACK_JOB_ID")
    if not job_id_str:
        await logger.aerror("missing SQLSTACK_JOB_ID environment variable")
        return 1

    try:
        job_id = UUID(job_id_str)
    except ValueError:
        await logger.aerror("invalid SQLSTACK_JOB_ID environment variable", value=job_id_str)
        return 1

    await logger.ainfo("cloud run worker starting", job_id=str(job_id))

    # Load job from database (authoritative source for kwargs)
    async with db_manager.provide_session(db) as driver:
        task_service = TaskService(driver=driver)
        job = await task_service.get_task(job_id)

    if not job:
        await logger.aerror("job not found in database", job_id=str(job_id))
        return 1

    function = job.function
    kwargs = job.data or {}

    await logger.ainfo("loaded job from database", job_id=str(job_id), function=function)

    # Load all job modules to populate registry
    load_jobs()
    registry = get_job_registry()

    # Get the registered task
    task = registry.get(function)
    if not task:
        await logger.aerror("unknown task function", function=function)
        async with db_manager.provide_session(db) as driver:
            task_service = TaskService(driver=driver)
            await task_service.fail_task(job_id, f"Unknown task: {function}", retry=False)
        return 1

    shutdown_event = asyncio.Event()
    heartbeat_task: asyncio.Task[None] | None = None

    try:
        # Claim the job
        async with db_manager.provide_session(db) as driver:
            task_service = TaskService(driver=driver)
            claimed = await task_service.claim_task(job_id)
            if not claimed:
                await logger.awarning("failed to claim job", job_id=str(job_id))
                return 1

        # Start heartbeat loop (parity with local worker)
        heartbeat_task = asyncio.create_task(_heartbeat_loop(job_id, shutdown_event))

        # Execute the task
        result = await task(**kwargs)

        # Mark as completed
        async with db_manager.provide_session(db) as driver:
            task_service = TaskService(driver=driver)
            await task_service.complete_task(job_id, result={"result": result} if result else None)

        await logger.ainfo("cloud run job completed", job_id=str(job_id))
        return 0  # noqa: TRY300

    except NonRetryableError as e:
        # Non-retryable errors: do NOT retry (parity with local worker)
        await logger.aexception("cloud run job failed (non-retryable)", job_id=str(job_id))
        async with db_manager.provide_session(db) as driver:
            task_service = TaskService(driver=driver)
            await task_service.fail_task(job_id, str(e), retry=False)
        return 1

    except Exception as e:
        # Retryable errors
        await logger.aexception("cloud run job failed", job_id=str(job_id))
        async with db_manager.provide_session(db) as driver:
            task_service = TaskService(driver=driver)
            await task_service.fail_task(job_id, str(e), retry=True)
        return 1

    finally:
        # Stop heartbeat
        shutdown_event.set()
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task


def main() -> None:
    """Entry point for Cloud Run container."""
    exit_code = asyncio.run(execute_cloudrun_job())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
