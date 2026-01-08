"""Job schemas for background tasks."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

import msgspec

from sqlstack.lib.schema import CamelizedBaseStruct


def _make_dict() -> dict[str, Any]:
    """Create empty dict for msgspec field default."""
    return {}


__all__ = ("Job", "JobCreate", "JobStats", "JobStatus", "JobUpdate")

JobStatus = Literal["pending", "running", "completed", "failed", "cancelled", "scheduled"]


class JobBase(CamelizedBaseStruct):
    """Base job schema."""

    function: str
    data: dict[str, Any] = msgspec.field(default_factory=_make_dict)
    status: JobStatus = "pending"
    priority: int = 0
    max_retries: int = 3


class JobCreate(JobBase):
    """Job creation schema."""

    key: str | None = None
    scheduled_at: datetime | None = None


class Job(JobBase, kw_only=True):
    """Full job schema."""

    id: UUID
    key: str | None = None
    retry_count: int = 0
    scheduled_at: datetime | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    heartbeat_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result: dict[str, Any] | None = None
    metadata: dict[str, Any] = msgspec.field(default_factory=_make_dict)


class JobUpdate(CamelizedBaseStruct):
    """Job update schema."""

    status: JobStatus | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result: dict[str, Any] | None = None
    retry_count: int | None = None


class JobStats(CamelizedBaseStruct):
    """Job statistics schema."""

    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    scheduled: int = 0
    total: int = 0
