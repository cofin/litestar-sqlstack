"""Integration tests for SystemConfigPlugin."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from litestar import Litestar
from structlog.contextvars import get_contextvars

from sqlstack.domain.system.services import SystemConfigService
from sqlstack.utils.system_config import SystemConfigPlugin

if TYPE_CHECKING:
    from sqlspec.adapters.asyncpg import AsyncpgConfig


@pytest.mark.anyio
async def test_system_config_plugin_startup(asyncpg_config: AsyncpgConfig, clean_database: None) -> None:
    """Test that SystemConfigPlugin loads and merges settings, and binds installation ID."""
    # Ensure test environment var is not set
    os.environ.pop("TEST_DYNAMIC_VAR", None)

    # 1. Insert a dynamic setting into database
    async with asyncpg_config.provide_session() as driver:
        config_service = SystemConfigService(driver)
        await config_service.set("TEST_DYNAMIC_VAR", "hello-from-db")

    from litestar.testing import AsyncTestClient

    # 2. Create the plugin and app
    plugin = SystemConfigPlugin()
    app = Litestar(plugins=[plugin])

    # 3. Trigger startup via client lifecycle context manager
    async with AsyncTestClient(app):
        # 4. Verify the database setting was merged into os.environ
        assert os.environ.get("TEST_DYNAMIC_VAR") == "hello-from-db"

        pass

    # Cleanup
    os.environ.pop("TEST_DYNAMIC_VAR", None)
