# pylint: disable=[invalid-name,import-outside-toplevel]
"""Application core plugin for Litestar configuration.

This plugin handles all application initialization including:
- OpenAPI configuration
- CORS and middleware setup
- Plugin registration
- Dishka dependency injection setup

Container creation is centralized in ioc.py - this plugin only sets up
the container with the Litestar application.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from litestar import Request
from litestar.di import Provide
from litestar.enums import RequestEncodingType
from litestar.openapi.config import OpenAPIConfig
from litestar.openapi.plugins import ScalarRenderPlugin
from litestar.params import Body, Parameter
from litestar.plugins import CLIPluginProtocol, InitPluginProtocol

from sqlstack.ioc import make_litestar_container
from sqlstack.lib.di import setup_dishka

if TYPE_CHECKING:
    from click import Group
    from litestar import Litestar
    from litestar.config.app import AppConfig

T = TypeVar("T")


class ApplicationCore(InitPluginProtocol, CLIPluginProtocol):
    """Application core configuration plugin.

    This class is responsible for configuring the main Litestar application with our routes, guards, and various plugins

    """

    __slots__ = ("app_slug",)
    app_slug: str

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        """Configure application for use with SQLAlchemy.

        Args:
            app_config: The :class:`AppConfig <litestar.config.app.AppConfig>` instance.

        Returns:
            The configured app config.
        """
        from uuid import UUID

        from litestar import WebSocket
        from litestar.channels import ChannelsPlugin
        from litestar.datastructures import State
        from sqlspec.adapters.asyncpg import AsyncpgDriver
        from sqlspec.driver import AsyncDriverAdapterBase
        from sqlspec.exceptions import UniqueViolationError

        from sqlstack import config
        from sqlstack.__metadata__ import __version__
        from sqlstack.domain.accounts import schemas as account_schemas
        from sqlstack.domain.accounts import security
        from sqlstack.domain.system import schemas as system_schemas
        from sqlstack.lib.exceptions import (
            ConflictError,
            NotFoundError,
            ValidationError,
            conflict_exception_handler,
            not_found_exception_handler,
            unique_violation_exception_handler,
            validation_exception_handler,
        )
        from sqlstack.lib.service import FilterTypes, OffsetPagination, SQLSpecAsyncService
        from sqlstack.lib.settings import get_settings
        from sqlstack.server import plugins

        settings = get_settings()
        self.app_slug = settings.app.slug
        app_config.debug = settings.app.DEBUG
        app_config.openapi_config = OpenAPIConfig(
            title=settings.app.NAME,
            version=__version__,
            components=[security.auth.openapi_components],
            security=[security.auth.security_requirement],
            render_plugins=[ScalarRenderPlugin(version="latest")],
        )
        app_config = security.auth.on_app_init(app_config)
        app_config.cors_config = config.cors
        app_config.stores = config.stores
        app_config.middleware.append(config.session_config.middleware)
        app_config.plugins.extend([
            plugins.structlog,
            plugins.granian,
            plugins.sqlspec,
            plugins.problem_details,
            plugins.worker,
            plugins.channels,
            plugins.domain,
            plugins.vite,
        ])
        app_config.signature_namespace.update({
            "RequestEncodingType": RequestEncodingType,
            "Body": Body,
            "State": State,
            "ChannelsPlugin": ChannelsPlugin,
            "WebSocket": WebSocket,
            "Parameter": Parameter,
            "Request": Request,
            "account_schemas": account_schemas,
            "system_schemas": system_schemas,
            "UUID": UUID,
            "FilterTypes": FilterTypes,
            "OffsetPagination": OffsetPagination,
            "SQLSpecAsyncService": SQLSpecAsyncService,
            "AsyncDriverAdapterBase": AsyncDriverAdapterBase,
            "AsyncpgDriver": AsyncpgDriver,
        })
        # Exception handlers
        app_config.exception_handlers = {
            NotFoundError: not_found_exception_handler,
            ValidationError: validation_exception_handler,
            ConflictError: conflict_exception_handler,
            UniqueViolationError: unique_violation_exception_handler,
            **app_config.exception_handlers,
        }
        # dependencies
        dependencies = {"current_user": Provide(security.provide_user, sync_to_thread=False)}
        app_config.dependencies.update(dependencies)

        # Dishka dependency injection setup
        container = make_litestar_container()

        async def _init_di(app: Litestar) -> None:
            setup_dishka(container, app)

        async def _shutdown_di(_app: Litestar) -> None:
            await container.close()

        app_config.on_startup.append(_init_di)
        app_config.on_shutdown.append(_shutdown_di)

        return app_config

    def on_cli_init(self, cli: Group) -> None:
        from sqlspec.extensions.litestar.cli import database_group

        from sqlstack.cli.commands import (
            assets_group,
            database_commands,
            manage_group,
            server_group,
            user_management_group,
            version_cmd,
        )
        from sqlstack.lib.settings import get_settings

        settings = get_settings()
        self.app_slug = settings.app.slug

        # Register database commands into the shared database group
        for cmd in database_commands:
            database_group.add_command(cmd)

        # Add all groups to the main CLI
        cli.add_command(server_group)
        cli.add_command(manage_group)
        cli.add_command(assets_group)
        cli.add_command(database_group)
        cli.add_command(user_management_group)
        cli.add_command(version_cmd)
