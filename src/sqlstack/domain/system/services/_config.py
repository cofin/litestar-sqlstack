"""System configuration service using SQLSpec."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlspec import sql

from sqlstack.lib.service import SQLSpecAsyncService

if TYPE_CHECKING:
    pass


class SystemConfigService(SQLSpecAsyncService):
    """Service for managing dynamic system configuration settings in the database."""

    async def get(self, key: str) -> str | None:
        """Get config value by key.

        Args:
            key: Configuration key

        Returns:
            Configuration value or None if not found
        """
        val = await self.driver.select_value_or_none(
            sql.select("value").from_("system_config").where_eq("key", key)
        )
        return str(val) if val is not None else None

    async def set(self, key: str, value: str, description: str | None = None) -> None:
        """Set config value. Updates if key already exists.

        Args:
            key: Configuration key
            value: Configuration value
            description: Optional description of the key
        """
        await self.driver.execute(
            """
            INSERT INTO system_config (key, value, description)
            VALUES (:key, :value, :description)
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value,
                description = COALESCE(:description, system_config.description),
                updated_at = NOW()
            """,
            key=key,
            value=value,
            description=description,
        )

    async def get_all(self) -> dict[str, str]:
        """Get all configurations as a key-value dictionary.

        Returns:
            Dictionary of configuration key-value pairs
        """
        rows = await self.driver.select(
            sql.select("key", "value").from_("system_config")
        )
        return {row["key"]: row["value"] for row in rows}

    async def delete(self, key: str) -> None:
        """Delete config setting by key.

        Args:
            key: Configuration key to delete
        """
        await self.driver.execute(
            sql.delete("system_config").where_eq("key", key)
        )
