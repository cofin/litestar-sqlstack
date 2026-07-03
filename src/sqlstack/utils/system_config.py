"""Litestar plugin to load system configurations from database on startup."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import structlog
from litestar.plugins import InitPluginProtocol
from structlog.contextvars import bind_contextvars

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.config.app import AppConfig

logger = structlog.get_logger()


class SystemConfigPlugin(InitPluginProtocol):
    """Litestar plugin that loads dynamic configurations from database.

    Runs first (position 0) at startup to merge database configurations into the
    environment and bind the unique installation ID to logger context.
    """

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        """Register the startup hook.

        Args:
            app_config: The Litestar app configuration.

        Returns:
            AppConfig: The updated app configuration.
        """
        if not app_config.on_startup:
            app_config.on_startup = []

        # Insert at position 0 to run before other startup tasks
        app_config.on_startup.insert(0, self._on_startup)
        return app_config

    async def _on_startup(self, app: Litestar) -> None:
        """Load and merge settings from system_config database table.

        Args:
            app: The Litestar application instance.
        """
        from sqlstack.config import db, db_manager
        from sqlstack.domain.system.services import InstallationService, SystemConfigService
        from sqlstack.lib.settings import Settings

        await logger.adebug("Loading system settings from database...")

        async with db_manager.provide_session(db) as driver:
            # 1. Fetch dynamic config settings
            config_service = SystemConfigService(driver)
            db_settings = await config_service.get_all()

            # 2. Merge database settings with environment settings
            for key, value in db_settings.items():
                os.environ[key] = value

            # 3. Clear settings environment cache so get_settings() re-evaluates
            Settings.from_env.cache_clear()

            # 4. Resolve installation ID and bind to logging context
            installation_service = InstallationService(driver)
            installation_id = await installation_service.get_id()
            bind_contextvars(installation_id=str(installation_id))

            await logger.ainfo("System settings loaded", installation_id=str(installation_id))
