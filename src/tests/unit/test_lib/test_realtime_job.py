"""Unit tests for realtime event-publishing sample job."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from sqlstack.domain.system.jobs._system import publish_heartbeat


class TestPublishHeartbeatJob:
    @pytest.mark.anyio
    async def test_publish_heartbeat_returns_result(self) -> None:
        """The heartbeat job should return a success result dict."""
        mock_publisher = AsyncMock()
        mock_publisher.publish_global_event = AsyncMock()

        with patch("sqlstack.domain.system.jobs._system._get_publisher", return_value=mock_publisher):
            result = await publish_heartbeat()

        assert result["status"] == "completed"
        assert "events_published" in result

    @pytest.mark.anyio
    async def test_publish_heartbeat_publishes_global_event(self) -> None:
        """The heartbeat job should call publish_global_event."""
        mock_publisher = AsyncMock()
        mock_publisher.publish_global_event = AsyncMock()

        with patch("sqlstack.domain.system.jobs._system._get_publisher", return_value=mock_publisher):
            await publish_heartbeat()

        mock_publisher.publish_global_event.assert_called_once()
        call_kwargs = mock_publisher.publish_global_event.call_args
        assert call_kwargs[1]["event_type"] == "system.heartbeat"

    @pytest.mark.anyio
    async def test_publish_heartbeat_graceful_without_backend(self) -> None:
        """The heartbeat job should not crash if no channels backend is available."""
        with patch("sqlstack.domain.system.jobs._system._get_publisher", return_value=None):
            result = await publish_heartbeat()

        assert result["status"] == "skipped"
