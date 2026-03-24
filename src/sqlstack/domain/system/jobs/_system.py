"""System-level background jobs."""

import asyncio
from typing import Any

from structlog import get_logger

from sqlstack.lib.jobs import register_job

__all__ = ("background_worker_task", "cleanup_old_sessions", "publish_heartbeat", "system_task", "system_upkeep")

logger = get_logger()


@register_job("system_upkeep")
async def system_upkeep() -> dict[str, Any]:
    """Perform regular system maintenance tasks.

    This job handles periodic maintenance operations.

    Returns:
        Job execution result
    """
    await logger.ainfo("performing system upkeep operations")
    await logger.ainfo("simulating a long running operation - sleeping for 60 seconds")
    await asyncio.sleep(60)
    await logger.ainfo("simulating an even longer running operation - sleeping for 120 seconds")
    await asyncio.sleep(120)
    await logger.ainfo("long running process complete")
    return {"status": "completed", "duration_seconds": 180}


@register_job("background_worker_task")
async def background_worker_task() -> dict[str, Any]:
    """Perform background worker task.

    Returns:
        Job execution result
    """
    await logger.ainfo("performing background worker task")
    await asyncio.sleep(20)
    await logger.ainfo("background worker task complete")
    return {"status": "completed", "duration_seconds": 20}


@register_job("system_task")
async def system_task() -> dict[str, Any]:
    """Perform simple system task.

    Returns:
        Job execution result
    """
    await logger.ainfo("performing simple system task")
    await asyncio.sleep(2)
    await logger.ainfo("system task complete")
    return {"status": "completed", "duration_seconds": 2}


@register_job(cron="0 2 * * *")  # Daily at 2 AM
async def cleanup_old_sessions() -> dict[str, Any]:
    """Clean up old sessions (scheduled daily at 2 AM).

    Returns:
        Job execution result with cleanup statistics
    """
    await logger.ainfo("cleaning up old sessions")
    # Simulate cleanup work
    await asyncio.sleep(5)
    # In a real implementation, this would call a service to clean up old sessions
    cleaned_count = 0  # Placeholder
    await logger.ainfo("session cleanup complete", cleaned=cleaned_count)
    return {"status": "completed", "sessions_cleaned": cleaned_count}


from sqlstack.lib.realtime import RealtimePublisher


def _get_publisher() -> RealtimePublisher | None:
    """Attempt to get a RealtimePublisher from the worker container.

    Returns None if no channels backend is available (e.g., during testing
    or when running without the channels plugin).
    """
    from sqlstack.lib.di import worker_container_var

    container = worker_container_var.get()
    if container is None:
        return None
    try:
        from litestar.channels.backends.memory import MemoryChannelsBackend

        backend = MemoryChannelsBackend(history=0)
        return RealtimePublisher(backend)
    except Exception:  # noqa: BLE001
        return None


@register_job("publish_heartbeat", interval=30)
async def publish_heartbeat() -> dict[str, Any]:
    """Publish a system heartbeat event to the global realtime channel.

    This demonstrates the pattern of a background job publishing events
    that are consumed by WebSocket clients via the stream controller.

    Returns:
        Job execution result
    """
    publisher = _get_publisher()
    if publisher is None:
        await logger.ainfo("no realtime backend available, skipping heartbeat")
        return {"status": "skipped", "events_published": 0}

    await publisher.publish_global_event(
        event_type="system.heartbeat",
        payload={"message": "system alive", "source": "heartbeat_job"},
    )

    await logger.ainfo("published system heartbeat event")
    return {"status": "completed", "events_published": 1}
