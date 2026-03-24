"""Unit tests for WebSocket streaming utilities."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlstack.lib.websockets import (
    RealtimeStreamMetrics,
    get_realtime_stream_metrics,
    reset_realtime_stream_metrics,
    _decode_message,
    _extract_idempotency_key,
)


class TestRealtimeStreamMetrics:
    def test_initial_values_are_zero(self) -> None:
        metrics = RealtimeStreamMetrics()
        snapshot = metrics.snapshot()
        assert all(v == 0 for v in snapshot.values())

    def test_snapshot_returns_dict(self) -> None:
        metrics = RealtimeStreamMetrics()
        metrics.messages_received = 5
        metrics.messages_delivered = 3
        snapshot = metrics.snapshot()
        assert snapshot["messages_received"] == 5
        assert snapshot["messages_delivered"] == 3

    def test_reset_clears_all_counters(self) -> None:
        metrics = RealtimeStreamMetrics()
        metrics.active_subscriptions = 10
        metrics.messages_received = 100
        metrics.reset()
        assert all(v == 0 for v in metrics.snapshot().values())


class TestDecodeMessage:
    def test_decode_json_string(self) -> None:
        result = _decode_message('{"key": "value"}', ["ch1"])
        assert result == {"key": "value"}

    def test_decode_json_bytes(self) -> None:
        result = _decode_message(b'{"key": "value"}', ["ch1"])
        assert result == {"key": "value"}

    def test_decode_bytearray(self) -> None:
        result = _decode_message(bytearray(b'{"key": "value"}'), ["ch1"])
        assert result == {"key": "value"}

    def test_decode_malformed_returns_none(self) -> None:
        result = _decode_message(b"not-json", ["ch1"])
        assert result is None

    def test_non_string_passthrough(self) -> None:
        data = {"already": "decoded"}
        result = _decode_message(data, ["ch1"])
        assert result is data


class TestExtractIdempotencyKey:
    def test_extract_from_nested_payload(self) -> None:
        msg = {"payload": {"idempotency_key": "abc123"}}
        assert _extract_idempotency_key(msg) == "abc123"

    def test_extract_camel_case(self) -> None:
        msg = {"payload": {"idempotencyKey": "def456"}}
        assert _extract_idempotency_key(msg) == "def456"

    def test_returns_none_when_missing(self) -> None:
        assert _extract_idempotency_key({"payload": {}}) is None

    def test_returns_none_for_non_dict(self) -> None:
        assert _extract_idempotency_key("not a dict") is None

    def test_returns_none_for_non_dict_payload(self) -> None:
        assert _extract_idempotency_key({"payload": "string"}) is None

    def test_returns_none_for_empty_key(self) -> None:
        assert _extract_idempotency_key({"payload": {"idempotency_key": ""}}) is None


class TestModuleLevelFunctions:
    def test_get_realtime_stream_metrics_returns_dict(self) -> None:
        snapshot = get_realtime_stream_metrics()
        assert isinstance(snapshot, dict)
        assert "active_subscriptions" in snapshot

    def test_reset_realtime_stream_metrics(self) -> None:
        reset_realtime_stream_metrics()
        snapshot = get_realtime_stream_metrics()
        assert all(v == 0 for v in snapshot.values())
