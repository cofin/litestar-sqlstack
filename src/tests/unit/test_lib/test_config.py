"""Unit tests for config lazy initialization."""

from __future__ import annotations

import sys
from unittest.mock import patch


def test_lazy_initialization() -> None:
    """Test that importing config does not trigger initialization until attribute access."""
    # Ensure config is not in sys.modules so we test the import behavior
    sys.modules.pop("sqlstack.config", None)

    # We mock out SQLSpec methods or Settings to check when they get called
    with patch("sqlspec.SQLSpec.add_config") as mock_add_config:
        # Import should be side-effect free
        import sqlstack.config

        # Should not have called add_config yet
        assert mock_add_config.call_count == 0

        # Accessing database config should trigger initialization
        _ = sqlstack.config.db

        # Should now have initialized
        assert mock_add_config.call_count > 0
