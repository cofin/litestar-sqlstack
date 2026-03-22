"""Realtime event publisher abstraction."""

from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog

from sqlstack.lib.realtime._contract import RealtimeActor, RealtimeChannels, RealtimeEntityRef, RealtimeEvent
from sqlstack.utils.serialization import to_json

if TYPE_CHECKING:
    from litestar.channels import ChannelsBackend

logger = structlog.get_logger()


class RealtimePublisher:
    """Publish typed realtime events through the configured channels backend."""

    def __init__(self, backend: "ChannelsBackend") -> None:
        self.backend = backend

    async def publish_event(self, event: RealtimeEvent, channel: str | None = None) -> None:
        """Publish a realtime event to a specific channel or scope-derived default."""
        resolved_channel = channel or self._resolve_channel(event)
        try:
            await self.backend.publish(data=to_json(event), channels=[resolved_channel])
        except RuntimeError as exc:
            if not self._is_backend_not_initialized_error(exc):
                raise
            logger.debug(
                "Realtime backend not initialized; skipping publish",
                event_type=event.event_type,
                scope=event.scope,
                channel=resolved_channel,
            )

    async def publish_team_event(
        self,
        team_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        *,
        topic: str = "events",
        actor: RealtimeActor | None = None,
        entity: RealtimeEntityRef | None = None,
        user_id: UUID | None = None,
    ) -> RealtimeEvent:
        """Build and publish a team-scoped realtime event."""
        event = RealtimeEvent(
            event_type=event_type,
            scope="team",
            team_id=team_id,
            user_id=user_id,
            actor=actor,
            entity=entity,
            payload=payload,
        )
        await self.publish_event(event, channel=RealtimeChannels.team(team_id, topic=topic))
        return event

    async def publish_user_event(
        self,
        user_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        *,
        topic: str = "events",
        actor: RealtimeActor | None = None,
        entity: RealtimeEntityRef | None = None,
    ) -> RealtimeEvent:
        """Build and publish a user-scoped realtime event."""
        event = RealtimeEvent(
            event_type=event_type, scope="user", user_id=user_id, actor=actor, entity=entity, payload=payload
        )
        await self.publish_event(event, channel=RealtimeChannels.user(user_id, topic=topic))
        return event

    async def publish_global_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        topic: str = "events",
        actor: RealtimeActor | None = None,
        entity: RealtimeEntityRef | None = None,
    ) -> RealtimeEvent:
        """Build and publish a global-scoped realtime event."""
        event = RealtimeEvent(event_type=event_type, scope="global", actor=actor, entity=entity, payload=payload)
        await self.publish_event(event, channel=RealtimeChannels.global_channel(topic=topic))
        return event

    @staticmethod
    def _resolve_channel(event: RealtimeEvent) -> str:
        """Resolve default channel from event scope."""
        if event.scope == "team":
            if event.team_id is None:
                msg = "Team-scoped realtime event requires team_id"
                raise ValueError(msg)
            return RealtimeChannels.team(event.team_id)
        if event.scope == "user":
            if event.user_id is None:
                msg = "User-scoped realtime event requires user_id"
                raise ValueError(msg)
            return RealtimeChannels.user(event.user_id)
        return RealtimeChannels.global_channel()

    @staticmethod
    def _is_backend_not_initialized_error(exc: RuntimeError) -> bool:
        """Return true when channels backend startup has not completed yet."""
        message = str(exc).lower()
        return "backend not yet initialized" in message or "forget to call on_startup" in message


__all__ = ("RealtimePublisher",)
