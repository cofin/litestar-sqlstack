"""Unit tests for WebSocket stream controller."""
from __future__ import annotations

from sqlstack.domain.system.controllers._stream import RealtimeStreamController


class TestRealtimeStreamController:
    def test_controller_has_correct_path(self) -> None:
        assert RealtimeStreamController.path == "/api/realtime"

    def test_controller_has_tags(self) -> None:
        assert "Realtime" in RealtimeStreamController.tags

    def test_controller_has_stream_method(self) -> None:
        assert hasattr(RealtimeStreamController, "stream_global_events")
