"""WebSocket streaming utilities with pub/sub, deduplication, and metrics."""
from typing import cast

import structlog
from litestar import WebSocket
from litestar.exceptions import WebSocketDisconnect

from sqlstack.utils.serialization import from_json

logger = structlog.get_logger()
_MAX_DEDUP_KEYS = 1024


class RealtimeStreamMetrics:
    """In-process counters for realtime stream health and delivery."""

    def __init__(self) -> None:
        self.active_subscriptions = 0
        self.messages_received = 0
        self.messages_delivered = 0
        self.messages_malformed = 0
        self.messages_deduplicated = 0
        self.disconnects = 0
        self.stream_errors = 0

    def snapshot(self) -> dict[str, int]:
        """Return an immutable metrics snapshot."""
        return {
            "active_subscriptions": self.active_subscriptions,
            "messages_received": self.messages_received,
            "messages_delivered": self.messages_delivered,
            "messages_malformed": self.messages_malformed,
            "messages_deduplicated": self.messages_deduplicated,
            "disconnects": self.disconnects,
            "stream_errors": self.stream_errors,
        }

    def reset(self) -> None:
        """Reset all counters."""
        self.active_subscriptions = 0
        self.messages_received = 0
        self.messages_delivered = 0
        self.messages_malformed = 0
        self.messages_deduplicated = 0
        self.disconnects = 0
        self.stream_errors = 0


_STREAM_METRICS = RealtimeStreamMetrics()


def get_realtime_stream_metrics() -> dict[str, int]:
    """Get current realtime stream diagnostics counters."""
    return _STREAM_METRICS.snapshot()


def reset_realtime_stream_metrics() -> None:
    """Reset realtime stream diagnostics counters."""
    _STREAM_METRICS.reset()


def _decode_message(message: object, channels: list[str]) -> object | None:
    """Decode serialized channel payloads, skipping malformed frames."""
    serialized_data: str | bytes | None
    if isinstance(message, (str, bytes)):
        serialized_data = message
    elif isinstance(message, bytearray):
        serialized_data = bytes(message)
    else:
        return message

    try:
        return cast("object", from_json(serialized_data))
    except Exception:  # noqa: BLE001
        logger.warning("Skipping malformed websocket payload", channels=channels)
        return None


def _extract_idempotency_key(payload: object) -> str | None:
    """Return idempotency key from event payload if available."""
    if not isinstance(payload, dict):
        return None
    event_payload = payload.get("payload")
    if not isinstance(event_payload, dict):
        return None

    key = event_payload.get("idempotency_key")
    if not isinstance(key, str) or not key:
        key = event_payload.get("idempotencyKey")
    if isinstance(key, str) and key:
        return key
    return None


async def stream_pubsub(socket: WebSocket, channels: list[str], *, history: int = 0) -> None:
    """Stream pub/sub messages to a WebSocket client.

    Handles disconnection and errors gracefully. The subscription is
    automatically cleaned up when the client disconnects or any error occurs.

    Args:
        socket: The WebSocket connection (must already be accepted).
        channels: List of pub/sub channel names to subscribe to.
        history: Number of historical messages to replay (default 0).
    """
    from sqlstack import config

    _STREAM_METRICS.active_subscriptions += 1
    session_received = 0
    session_delivered = 0
    session_malformed = 0
    session_deduplicated = 0

    try:
        seen_keys: list[str] = []
        seen_key_set: set[str] = set()

        async with config.channels.start_subscription(channels, history=history) as subscriber:
            async for message in subscriber.iter_events():
                _STREAM_METRICS.messages_received += 1
                session_received += 1

                payload = _decode_message(message, channels)
                if payload is None:
                    _STREAM_METRICS.messages_malformed += 1
                    session_malformed += 1
                    continue

                idempotency_key = _extract_idempotency_key(payload)
                if idempotency_key is not None:
                    if idempotency_key in seen_key_set:
                        _STREAM_METRICS.messages_deduplicated += 1
                        session_deduplicated += 1
                        continue
                    seen_key_set.add(idempotency_key)
                    seen_keys.append(idempotency_key)
                    if len(seen_keys) > _MAX_DEDUP_KEYS:
                        removed = seen_keys.pop(0)
                        seen_key_set.discard(removed)

                await socket.send_json(payload)
                _STREAM_METRICS.messages_delivered += 1
                session_delivered += 1
    except WebSocketDisconnect:
        _STREAM_METRICS.disconnects += 1
    except Exception:  # noqa: BLE001
        _STREAM_METRICS.stream_errors += 1
        await logger.aexception("WebSocket stream error", channels=channels)
    finally:
        _STREAM_METRICS.active_subscriptions = max(0, _STREAM_METRICS.active_subscriptions - 1)
        await logger.adebug(
            "Realtime stream session summary",
            channels=channels,
            received=session_received,
            delivered=session_delivered,
            malformed=session_malformed,
            deduplicated=session_deduplicated,
        )


__all__ = ("get_realtime_stream_metrics", "reset_realtime_stream_metrics", "stream_pubsub")
