"""Unit tests for realtime catalog and contract utilities."""
from __future__ import annotations

from uuid import uuid4

import pytest

from sqlstack.lib.realtime import (
    RealtimeChannels,
    RealtimeEvent,
    build_task_idempotency_key,
    build_team_idempotency_key,
)


class TestBuildTaskIdempotencyKey:
    def test_basic_key(self) -> None:
        key = build_task_idempotency_key("started", "task-123")
        assert key == "started:task-123"

    def test_key_with_attempt(self) -> None:
        key = build_task_idempotency_key("failed", "task-456", attempt=3)
        assert key == "failed:task-456:3"

    def test_key_without_attempt(self) -> None:
        key = build_task_idempotency_key("completed", "task-789")
        assert ":" in key
        assert key.count(":") == 1


class TestBuildTeamIdempotencyKey:
    def test_basic_key(self) -> None:
        key = build_team_idempotency_key("mutation", "team-abc")
        assert key == "mutation:team-abc"

    def test_key_with_attempt(self) -> None:
        key = build_team_idempotency_key("mutation", "team-abc", attempt=2)
        assert key == "mutation:team-abc:2"


class TestRealtimeChannels:
    def test_team_channel(self) -> None:
        team_id = uuid4()
        channel = RealtimeChannels.team(team_id)
        assert channel == f"team:{team_id}:events"

    def test_team_channel_custom_topic(self) -> None:
        team_id = uuid4()
        channel = RealtimeChannels.team(team_id, topic="logs")
        assert channel == f"team:{team_id}:logs"

    def test_user_channel(self) -> None:
        user_id = uuid4()
        channel = RealtimeChannels.user(user_id)
        assert channel == f"user:{user_id}:events"

    def test_global_channel(self) -> None:
        channel = RealtimeChannels.global_channel()
        assert channel == "global:events"

    def test_global_channel_custom_topic(self) -> None:
        channel = RealtimeChannels.global_channel(topic="alerts")
        assert channel == "global:alerts"


class TestRealtimeEvent:
    def test_team_event_requires_team_id(self) -> None:
        with pytest.raises(ValueError, match="team_id is required"):
            RealtimeEvent(event_type="task.status.updated", scope="team")

    def test_user_event_requires_user_id(self) -> None:
        with pytest.raises(ValueError, match="user_id is required"):
            RealtimeEvent(event_type="user.notification.created", scope="user")

    def test_global_event_no_extra_required(self) -> None:
        event = RealtimeEvent(event_type="global.notification.broadcast", scope="global")
        assert event.scope == "global"

    def test_team_event_valid(self) -> None:
        team_id = uuid4()
        event = RealtimeEvent(event_type="task.status.updated", scope="team", team_id=team_id)
        assert event.team_id == team_id
        assert event.schema_version == "1.0"
