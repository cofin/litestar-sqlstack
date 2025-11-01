# pylint: disable=[invalid-name,import-outside-toplevel]
from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from litestar import Request
from litestar.di import Provide
from litestar.enums import RequestEncodingType
from litestar.openapi.config import OpenAPIConfig
from litestar.openapi.plugins import ScalarRenderPlugin
from litestar.params import Body, Parameter
from litestar.plugins import CLIPluginProtocol, InitPluginProtocol

from sqlstack.lib.di import setup_dishka
from sqlstack.providers import build_container

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

        from sqlstack import config
        from sqlstack import schemas as s
        from sqlstack.__metadata__ import __version__
        from sqlstack.lib.settings import get_settings
        from sqlstack.server import plugins, routes, security
        from sqlstack.services import FilterTypes, OffsetPagination, SQLSpecService

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
        app_config.plugins.extend([plugins.structlog, plugins.granian, plugins.sqlspec, plugins.problem_details])
        app_config.route_handlers.extend([
            routes.AccessController,
            routes.ProfileController,
            routes.RoleController,
            routes.SystemController,
            routes.UserController,
            routes.UserRoleController,
            routes.WebController,
        ])
        app_config.signature_namespace.update({
            "RequestEncodingType": RequestEncodingType,
            "Body": Body,
            "State": State,
            "ChannelsPlugin": ChannelsPlugin,
            "WebSocket": WebSocket,
            "Parameter": Parameter,
            "Request": Request,
            "s": s,
            "UUID": UUID,
            "FilterTypes": FilterTypes,
            "OffsetPagination": OffsetPagination,
            "SQLSpecService": SQLSpecService,
            "AsyncDriverAdapterBase": AsyncDriverAdapterBase,
            "AsyncpgDriver": AsyncpgDriver,
        })
        # dependencies
        dependencies = {"current_user": Provide(security.provide_user, sync_to_thread=False)}
        app_config.dependencies.update(dependencies)

        # Dishka dependency injection setup
        container = build_container()

        async def _init_di(app: Litestar) -> None:
            setup_dishka(container, app)

        async def _shutdown_di(_app: Litestar) -> None:
            await container.close()

        app_config.on_startup.append(_init_di)
        app_config.on_shutdown.append(_shutdown_di)

        return app_config

    def on_cli_init(self, cli: Group) -> None:
        from sqlspec.extensions.litestar.cli import database_group

        from sqlstack.cli.commands import export_fixtures_cmd, load_fixtures_cmd, user_management_group
        from sqlstack.lib.settings import get_settings

        settings = get_settings()
        self.app_slug = settings.app.slug
        database_group.add_command(load_fixtures_cmd)
        database_group.add_command(export_fixtures_cmd)

        cli.add_command(database_group)
        cli.add_command(user_management_group)
