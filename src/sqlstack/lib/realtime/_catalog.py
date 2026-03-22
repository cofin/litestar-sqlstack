"""Task producer mutation catalog and idempotency helpers."""

from enum import StrEnum


class TaskEventType(StrEnum):
    """Canonical task event types for lifecycle producers."""

    TASK_QUEUED = "task.status.queued"
    TASK_STARTED = "task.status.started"
    TASK_COMPLETED = "task.status.completed"
    TASK_FAILED = "task.status.failed"
    TASK_CANCELLED = "task.status.cancelled"
    TASK_LOG_CREATED = "task.log.created"
    SYSTEM_HEARTBEAT = "system.heartbeat"


class TeamEventType(StrEnum):
    """Canonical team event types for lifecycle producers."""

    TEAM_MUTATION = "team.status.updated"


TASK_MUTATION_EVENT_MAP: dict[str, TaskEventType] = {
    "task.status.queued": TaskEventType.TASK_QUEUED,
    "task.status.started": TaskEventType.TASK_STARTED,
    "task.status.completed": TaskEventType.TASK_COMPLETED,
    "task.status.failed": TaskEventType.TASK_FAILED,
    "task.status.cancelled": TaskEventType.TASK_CANCELLED,
    "task.log.created": TaskEventType.TASK_LOG_CREATED,
    "system.heartbeat": TaskEventType.SYSTEM_HEARTBEAT,
}


def build_team_idempotency_key(transition: str, team_id: str, attempt: int | None = None) -> str:
    """Build deterministic idempotency key for team transition events."""
    base = f"{transition}:{team_id}"
    if attempt is None:
        return base
    return f"{base}:{attempt}"


__all__ = ("TASK_MUTATION_EVENT_MAP", "TaskEventType", "TeamEventType", "build_task_idempotency_key", "build_team_idempotency_key")
