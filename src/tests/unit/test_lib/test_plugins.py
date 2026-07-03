"""Unit tests for plugins lazy loading."""

from __future__ import annotations

import pytest
from litestar.plugins import InitPluginProtocol


def test_plugins_lazy_loading_and_exports() -> None:
    """Verify that plugins are lazy-loaded and all required plugins are exposed."""
    import sqlstack.config
    from sqlstack.server import plugins

    # 1. Reset config and verify uninitialized
    sqlstack.config._reset()
    plugins._reset()
    assert not sqlstack.config._initialized

    # 2. Accessing system_config should load SystemConfigPlugin
    system_config = plugins.system_config
    assert isinstance(system_config, InitPluginProtocol)
    assert system_config.__class__.__name__ == "SystemConfigPlugin"

    # 3. Accessing structlog should trigger initialization
    structlog_plugin = plugins.structlog
    assert structlog_plugin is not None
    assert sqlstack.config._initialized

    # 4. Verify all expected plugins are accessible
    assert plugins.granian is not None
    assert plugins.problem_details is not None
    assert plugins.worker is not None
    assert plugins.db_plugin is not None
    assert plugins.sqlspec is plugins.db_plugin  # alias check
    assert plugins.vite is not None
    assert plugins.domain is not None
    assert plugins.mcp is not None

    # 5. Reset and check uninitialized again
    sqlstack.config._reset()
    plugins._reset()
    assert not sqlstack.config._initialized
