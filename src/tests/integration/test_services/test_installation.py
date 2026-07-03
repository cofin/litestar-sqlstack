"""Integration tests for InstallationService."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from sqlstack.domain.system.services import InstallationService, SystemConfigService

if TYPE_CHECKING:
    from sqlspec.adapters.asyncpg import AsyncpgDriver


@pytest.fixture
def system_config_service(driver: AsyncpgDriver) -> SystemConfigService:
    """Provide SystemConfigService fixture."""
    return SystemConfigService(driver)


@pytest.fixture
def installation_service(driver: AsyncpgDriver) -> InstallationService:
    """Provide InstallationService fixture."""
    return InstallationService(driver)


@pytest.mark.anyio
async def test_installation_service(
    installation_service: InstallationService,
    system_config_service: SystemConfigService,
    clean_database: None,
) -> None:
    """Test resolving and caching installation ID."""
    # Check that system config is initially empty
    assert await system_config_service.get("installation_id") is None

    # Resolve installation ID
    inst_id1 = await installation_service.get_id()
    assert isinstance(inst_id1, UUID)

    # Resolve again - should be cached / same
    inst_id2 = await installation_service.get_id()
    assert inst_id1 == inst_id2

    # Check that it got saved in the database
    db_val = await system_config_service.get("installation_id")
    assert db_val == str(inst_id1)
