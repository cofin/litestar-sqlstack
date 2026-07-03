"""Unit tests for config lazy initialization."""

from __future__ import annotations

import sys
from unittest.mock import patch


def test_lazy_initialization() -> None:
    """Test that importing config does not trigger initialization until attribute access."""
    # Ensure config is not in sys.modules so we test the import behavior
    sys.modules.pop("sqlstack.config", None)

    # We mock get_settings to check when it gets called
    with patch("sqlstack.config.get_settings") as mock_get_settings:
        # Import should be side-effect free
        import sqlstack.config

        # Should not have called get_settings yet
        assert mock_get_settings.call_count == 0

        # Accessing database config should trigger initialization
        try:
            _ = sqlstack.config.db
        except Exception:
            # We just want to check if the initialization was triggered, not if it succeeded with mock
            pass

        # Should now have initialized
        assert mock_get_settings.call_count == 1

        # Accessing another attribute should not call get_settings again
        try:
            _ = sqlstack.config.csrf
        except Exception:
            pass

        assert mock_get_settings.call_count == 1

        # Trigger reset
        sqlstack.config._reset()

        # Accessing again should trigger initialization again
        try:
            _ = sqlstack.config.csrf
        except Exception:
            pass

        assert mock_get_settings.call_count == 2
