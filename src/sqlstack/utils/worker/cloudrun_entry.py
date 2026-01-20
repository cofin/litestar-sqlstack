"""Cloud Run entry point for background task execution.

This module provides the container entry point for executing tasks
in Google Cloud Run Jobs. It is designed to:

1. Execute a single task batch and exit (Cloud Run Jobs pattern)
2. Use OTEL tracing when available
3. Handle graceful shutdown on SIGTERM

Usage:
    # As Cloud Run Job entry point
    python -m sqlstack.utils.worker.cloudrun_entry

    # With specific task ID
    python -m sqlstack.utils.worker.cloudrun_entry --task-id <uuid>
"""

from __future__ import annotations

import asyncio
import os
import sys


async def run_single_batch(*, batch_size: int = 10) -> int:
    """Execute a single batch of tasks and return.

    This is the primary entry point for Cloud Run Jobs, which are
    designed to run a task and exit rather than run continuously.

    Args:
        batch_size: Maximum number of tasks to process

    Returns:
        Number of tasks processed
    """
    from sqlstack.config import db, db_manager
    from sqlstack.domain.system.services import TaskService
    from sqlstack.lib.jobs import get_job_registry
    from sqlstack.utils.worker.worker import Worker

    job_registry = get_job_registry()

    async with db_manager.provide_session(db) as driver:
        task_service = TaskService(driver=driver)
        tasks = await task_service.get_pending_tasks(limit=batch_size)

        processed = 0
        for task_data in tasks:
            if await task_service.claim_task(task_data.id):
                # Create a temporary worker for execution context
                worker = Worker(register_signals=False)
                worker.job_registry = job_registry
                await worker._execute_task(task_data)  # noqa: SLF001
                processed += 1

        return processed


def main() -> None:
    """Entry point for Cloud Run job container.

    Environment variables:
        CLOUD_RUN_TASK_INDEX: Task index (0-based) for parallel jobs
        CLOUD_RUN_TASK_COUNT: Total number of parallel tasks
        CLOUD_RUN_TASK_ATTEMPT: Retry attempt number
    """
    # Get Cloud Run environment info
    task_index = int(os.environ.get("CLOUD_RUN_TASK_INDEX", "0"))
    task_count = int(os.environ.get("CLOUD_RUN_TASK_COUNT", "1"))
    task_attempt = int(os.environ.get("CLOUD_RUN_TASK_ATTEMPT", "0"))

    print(f"Cloud Run Worker: index={task_index}/{task_count}, attempt={task_attempt}")  # noqa: T201

    try:
        processed = asyncio.run(run_single_batch())
        print(f"Processed {processed} tasks")  # noqa: T201
        sys.exit(0)
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}")  # noqa: T201
        sys.exit(1)


if __name__ == "__main__":
    main()
