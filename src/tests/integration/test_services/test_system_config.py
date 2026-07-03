"""Integration tests for SystemConfigService."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from sqlstack.domain.system.services import SystemConfigService

if TYPE_CHECKING:
    from sqlspec.adapters.asyncpg import AsyncpgDriver


@pytest.fixture
def system_config_service(driver: AsyncpgDriver) -> SystemConfigService:
    """Provide SystemConfigService fixture."""
    return SystemConfigService(driver)


@pytest.mark.anyio
async def test_system_config_lifecycle(system_config_service: SystemConfigService, clean_database: None) -> None:
    """Test getting, setting, list, and deleting system config values."""
    # Initially should be empty
    all_configs = await system_config_service.get_all()
    assert all_configs == {}

    # Set key1
    await system_config_service.set("key1", "value1", description="First config")
    
    # Get key1
    val = await system_config_service.get("key1")
    assert val == "value1"

    # Set key2
    await system_config_service.set("key2", "value2")

    # Get all should have both
    all_configs = await system_config_service.get_all()
    assert all_configs == {"key1": "value1", "key2": "value2"}

    # Update key1
    await system_config_service.set("key1", "value1_updated")
    assert await system_config_service.get("key1") == "value1_updated"

    # Delete key1
    await system_config_service.delete("key1")
    assert await system_config_service.get("key1") is None

    # Get all should have only key2
    all_configs = await system_config_service.get_all()
    assert all_configs == {"key2": "value2"}
