"""Job schemas for background tasks."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

import msgspec

from sqlstack.lib.schema import CamelizedBaseStruct


def _make_dict() -> dict[str, Any]:
    """Create empty dict for msgspec field default."""
    return {}


__all__ = (
    "Job",
    "JobCreate",
    "JobLog",
    "JobLogCreate",
    "JobLogLevel",
    "JobLogStageSummary",
    "JobLogSummary",
    "JobStats",
    "JobStatus",
    "JobUpdate",
)

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


class JobLogBase(CamelizedBaseStruct):
    """Base job log schema."""

    job_id: UUID
    stage: str = "processing"
    level: JobLogLevel = "INFO"
    message: str
    detail: dict[str, Any] = msgspec.field(default_factory=_make_dict)
    sequence: int = 0
    duration_ms: int | None = None
    team_id: UUID | None = None


class JobLogCreate(JobLogBase):
    """Job log creation schema."""


class JobLog(JobLogBase, kw_only=True):
    """Full job log schema."""

    id: UUID
    created_at: datetime


class JobLogStageSummary(CamelizedBaseStruct):
    """Summary of log entries for a specific job stage."""

    stage: str
    level: JobLogLevel
    entry_count: int
    duration_ms: int | None = None


class JobLogSummary(CamelizedBaseStruct):
    """Aggregated summary of all log entries for a job."""

    job_id: UUID
    total_entries: int
    stages: list[JobLogStageSummary]
    has_errors: bool = False
    has_warnings: bool = False
    total_duration_ms: int | None = None
