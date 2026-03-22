"""Canonical realtime event contract and channel taxonomy."""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

import msgspec

from sqlstack.lib.schema import CamelizedBaseStruct

RealtimeScope = Literal["team", "user", "global"]
RealtimeEventType = Literal[
    "task.status.updated",
    "task.log.created",
    "system.heartbeat",
    "user.notification.created",
    "global.notification.broadcast",
]

REALTIME_SCHEMA_VERSION = "1.0"
REALTIME_SCOPE_ACL: dict[RealtimeScope, str] = {
    "team": "team-member-or-superuser",
    "user": "authenticated-subject-only",
    "global": "role-policy-authorized",
}


class RealtimeChannels:
    """Channel name factories for team/user/global realtime streams."""

    @staticmethod
    def team(team_id: UUID, topic: str = "events") -> str:
        """Return team-scoped channel name."""
        return f"team:{team_id}:{topic}"

    @staticmethod
    def user(user_id: UUID, topic: str = "events") -> str:
        """Return user-scoped channel name."""
        return f"user:{user_id}:{topic}"

    @staticmethod
    def global_channel(topic: str = "events") -> str:
        """Return global/system channel name."""
        return f"global:{topic}"


class RealtimeActor(CamelizedBaseStruct, kw_only=True):
    """Actor metadata for a realtime event."""

    user_id: UUID | None = None
    source: Literal["user", "system"] = "system"


class RealtimeEntityRef(CamelizedBaseStruct, kw_only=True):
    """Entity reference associated with a realtime event."""

    type: str
    id: str


class RealtimeEvent(CamelizedBaseStruct, kw_only=True):
    """Canonical realtime event envelope."""

    schema_version: str = REALTIME_SCHEMA_VERSION
    event_type: RealtimeEventType | str
    scope: RealtimeScope
    published_at: datetime = msgspec.field(default_factory=lambda: datetime.now(UTC))
    team_id: UUID | None = None
    user_id: UUID | None = None
    actor: RealtimeActor | None = None
    entity: RealtimeEntityRef | None = None
    payload: dict[str, Any] = msgspec.field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate scope-specific references required by the contract."""
        if self.scope == "team" and self.team_id is None:
            msg = "team_id is required for team scope events"
            raise ValueError(msg)
        if self.scope == "user" and self.user_id is None:
            msg = "user_id is required for user scope events"
            raise ValueError(msg)


__all__ = (
    "REALTIME_SCHEMA_VERSION",
    "REALTIME_SCOPE_ACL",
    "RealtimeActor",
    "RealtimeChannels",
    "RealtimeEntityRef",
    "RealtimeEvent",
    "RealtimeEventType",
    "RealtimeScope",
)
