"""Installation resolution service using SQLSpec."""

from __future__ import annotations

import uuid
from uuid import UUID

from sqlspec import sql

from sqlstack.lib.service import SQLSpecAsyncService


class InstallationService(SQLSpecAsyncService):
    """Service for resolving and caching the installation ID."""

    _cached_id: UUID | None = None

    async def get_id(self) -> UUID:
        """Resolve the installation ID, generating and persisting a new one if not found.

        Returns:
            The resolved installation ID UUID.
        """
        if InstallationService._cached_id is not None:
            return InstallationService._cached_id

        val = await self.driver.select_value_or_none(
            sql.select("value").from_("system_config").where_eq("key", "installation_id")
        )
        if val is not None:
            InstallationService._cached_id = UUID(str(val))
            return InstallationService._cached_id

        new_id = uuid.uuid4()
        await self.driver.execute(
            """
            INSERT INTO system_config (key, value, description)
            VALUES ('installation_id', :value, 'System installation ID')
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value,
                updated_at = NOW()
            """,
            value=str(new_id),
        )
        InstallationService._cached_id = new_id
        return new_id
