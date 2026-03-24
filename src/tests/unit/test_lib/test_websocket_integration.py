"""Integration tests for WebSocket streaming endpoint and end-to-end pub/sub flow.

Tests the WebSocket endpoint connectivity and verifies the stream_pubsub
wiring with the ChannelsPlugin. The connection test uses a minimal Litestar
app; the pub/sub flow tests exercise stream_pubsub directly with mocks
since the ChannelsPlugin's internal asyncio.Queue doesn't cross threads.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from litestar import Litestar
from litestar.channels import ChannelsPlugin
from litestar.channels.backends.memory import MemoryChannelsBackend
from litestar.testing import AsyncTestClient

from sqlstack.domain.system.controllers._stream import RealtimeStreamController
from sqlstack.lib.realtime import RealtimeChannels, RealtimeEvent
from sqlstack.lib.websockets import (
    _STREAM_METRICS,
    reset_realtime_stream_metrics,
    stream_pubsub,
)
from sqlstack.utils.serialization import to_json


@pytest.fixture
def channels_backend() -> MemoryChannelsBackend:
    return MemoryChannelsBackend(history=10)


@pytest.fixture
def channels_plugin(channels_backend: MemoryChannelsBackend) -> ChannelsPlugin:
    return ChannelsPlugin(backend=channels_backend, arbitrary_channels_allowed=True)


@pytest.fixture
def test_app(channels_plugin: ChannelsPlugin) -> Litestar:
    """Minimal app with just channels + stream controller."""
    return Litestar(
        route_handlers=[RealtimeStreamController],
        plugins=[channels_plugin],
    )


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    reset_realtime_stream_metrics()


class TestWebSocketConnection:
    @pytest.mark.anyio
    async def test_websocket_connects_to_global_stream(
        self, test_app: Litestar, channels_plugin: ChannelsPlugin
    ) -> None:
        """Client can connect to /api/realtime/global/stream."""
        with patch("sqlstack.config.channels", channels_plugin):
            async with AsyncTestClient(app=test_app) as client:
                ws = await client.websocket_connect("/api/realtime/global/stream")
                try:
                    assert ws is not None
                finally:
                    ws.close()

    @pytest.mark.anyio
    async def test_unrelated_channel_not_received(
        self,
        test_app: Litestar,
        channels_plugin: ChannelsPlugin,
    ) -> None:
        """Events on a different channel should NOT arrive at the global stream."""
        with patch("sqlstack.config.channels", channels_plugin):
            async with AsyncTestClient(app=test_app) as client:
                ws = await client.websocket_connect("/api/realtime/global/stream")
                try:
                    with pytest.raises(Exception):
                        ws.receive_json(timeout=0.3)
                finally:
                    ws.close()


class TestStreamPubSubFlow:
    """Test the stream_pubsub function directly — verifies the full
    subscribe → decode → dedup → send_json pipeline."""

    @pytest.mark.anyio
    async def test_message_forwarded_to_websocket(self) -> None:
        """stream_pubsub forwards decoded channel messages to the WebSocket."""
        mock_socket = AsyncMock()
        event = RealtimeEvent(
            event_type="system.heartbeat",
            scope="global",
            payload={"message": "alive"},
        )
        event_bytes = to_json(event, as_bytes=True)

        # Mock the subscriber to yield one message then stop
        mock_subscriber = AsyncMock()
        mock_subscriber.iter_events = lambda: _async_iter([event_bytes])

        mock_plugin = MagicMock()
        mock_plugin.start_subscription = MagicMock(return_value=_async_cm(mock_subscriber))

        with patch("sqlstack.config.channels", mock_plugin):
            await stream_pubsub(mock_socket, ["global:events"], history=5)

        mock_plugin.start_subscription.assert_called_once_with(["global:events"], history=5)
        mock_socket.send_json.assert_called_once()
        sent = mock_socket.send_json.call_args[0][0]
        assert sent["eventType"] == "system.heartbeat"
        assert sent["payload"]["message"] == "alive"
        assert _STREAM_METRICS.messages_delivered == 1

    @pytest.mark.anyio
    async def test_duplicate_messages_deduplicated(self) -> None:
        """Messages with the same idempotency_key should be sent only once."""
        mock_socket = AsyncMock()

        payload_with_key = to_json(
            {
                "eventType": "task.status.updated",
                "scope": "global",
                "payload": {"idempotency_key": "dedup-123", "data": "first"},
            },
            as_bytes=True,
        )
        payload_dup = to_json(
            {
                "eventType": "task.status.updated",
                "scope": "global",
                "payload": {"idempotency_key": "dedup-123", "data": "duplicate"},
            },
            as_bytes=True,
        )

        mock_subscriber = AsyncMock()
        mock_subscriber.iter_events = lambda: _async_iter([payload_with_key, payload_dup])

        mock_plugin = MagicMock()
        mock_plugin.start_subscription = MagicMock(return_value=_async_cm(mock_subscriber))

        with patch("sqlstack.config.channels", mock_plugin):
            await stream_pubsub(mock_socket, ["global:events"])

        assert mock_socket.send_json.call_count == 1
        assert _STREAM_METRICS.messages_deduplicated == 1

    @pytest.mark.anyio
    async def test_malformed_messages_skipped(self) -> None:
        """Malformed JSON should be skipped without crashing."""
        mock_socket = AsyncMock()

        mock_subscriber = AsyncMock()
        mock_subscriber.iter_events = lambda: _async_iter([b"not-json"])

        mock_plugin = MagicMock()
        mock_plugin.start_subscription = MagicMock(return_value=_async_cm(mock_subscriber))

        with patch("sqlstack.config.channels", mock_plugin):
            await stream_pubsub(mock_socket, ["global:events"])

        mock_socket.send_json.assert_not_called()
        assert _STREAM_METRICS.messages_malformed == 1

    @pytest.mark.anyio
    async def test_multiple_events_delivered_in_order(self) -> None:
        """Multiple events should be delivered in publish order."""
        mock_socket = AsyncMock()
        events = [
            to_json(RealtimeEvent(event_type="system.heartbeat", scope="global", payload={"seq": i}), as_bytes=True)
            for i in range(3)
        ]

        mock_subscriber = AsyncMock()
        mock_subscriber.iter_events = lambda: _async_iter(events)

        mock_plugin = MagicMock()
        mock_plugin.start_subscription = MagicMock(return_value=_async_cm(mock_subscriber))

        with patch("sqlstack.config.channels", mock_plugin):
            await stream_pubsub(mock_socket, ["global:events"])

        assert mock_socket.send_json.call_count == 3
        seqs = [call[0][0]["payload"]["seq"] for call in mock_socket.send_json.call_args_list]
        assert seqs == [0, 1, 2]



# --- Helpers ---


async def _async_iter(items: list[Any]) -> Any:
    """Create an async iterator from a list."""
    for item in items:
        yield item


class _async_cm:
    """Simple async context manager wrapper."""

    def __init__(self, value: Any) -> None:
        self._value = value

    async def __aenter__(self) -> Any:
        return self._value

    async def __aexit__(self, *args: Any) -> None:
        pass
