# pylint: disable=[invalid-name,import-outside-toplevel]
from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from litestar.di import Provide
from litestar.openapi.config import OpenAPIConfig
from litestar.openapi.plugins import ScalarRenderPlugin
from litestar.plugins import CLIPluginProtocol, InitPluginProtocol
from litestar.security.jwt import OAuth2Login

if TYPE_CHECKING:
    from click import Group
    from litestar.config.app import AppConfig


T = TypeVar("T")


class ApplicationCore(InitPluginProtocol, CLIPluginProtocol):
    """Application core configuration plugin.

    This class is responsible for configuring the main Litestar application with our routes, guards, and various plugins

    """

    __slots__ = ("app_slug",)
    app_slug: str

    def on_cli_init(self, cli: Group) -> None:
        from sqlstack.cli.commands import user_management_group
        from sqlstack.lib.settings import get_settings

        settings = get_settings()
        self.app_slug = settings.app.slug
        cli.add_command(user_management_group)

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        """Configure application for use with SQLAlchemy.

        Args:
            app_config: The :class:`AppConfig <litestar.config.app.AppConfig>` instance.

        Returns:
            The configured app config.
        """

        from uuid import UUID

        from litestar.enums import RequestEncodingType
        from litestar.params import Body, Parameter
        from litestar.security.jwt import Token

        from sqlstack import config
        from sqlstack import schemas as s
        from sqlstack.__metadata__ import __version__
        from sqlstack.lib.settings import get_settings
        from sqlstack.server import plugins, routes, security
        from sqlstack.services import (
            EmailVerificationService,
            PasswordResetService,
            RoleService,
            TagService,
            TeamInvitationService,
            TeamMemberService,
            TeamService,
            UserOAuthAccountService,
            UserRoleService,
            UserService,
        )
        from sqlstack.services._base import OffsetPagination

        settings = get_settings()
        self.app_slug = settings.app.slug
        app_config.debug = settings.app.DEBUG
        # openapi
        app_config.openapi_config = OpenAPIConfig(
            title=settings.app.NAME,
            version=__version__,
            components=[security.auth.openapi_components],
            security=[security.auth.security_requirement],
            render_plugins=[ScalarRenderPlugin(version="latest")],
        )
        # jwt auth (updates openapi config)
        app_config = security.auth.on_app_init(app_config)
        # security
        app_config.cors_config = config.cors
        # plugins
        app_config.plugins.extend(
            [
                plugins.structlog,
                plugins.granian,
                plugins.sqlspec,
                plugins.problem_details,
            ],
        )

        # routes
        app_config.route_handlers.extend(
            [
                routes.AccessController,
                routes.ProfileController,
                routes.RoleController,
                routes.SystemController,
                routes.TagController,
                routes.TeamController,
                routes.TeamInvitationController,
                routes.TeamMemberController,
                routes.UserController,
                routes.UserRoleController,
                routes.WebController,
            ]
        )
        # signatures
        app_config.signature_namespace.update(
            {
                "Token": Token,
                "OAuth2Login": OAuth2Login,
                "RequestEncodingType": RequestEncodingType,
                "Body": Body,
                "Parameter": Parameter,
                "s": s,
                "UUID": UUID,
                "EmailVerificationService": EmailVerificationService,
                "PasswordResetService": PasswordResetService,
                "RoleService": RoleService,
                "TagService": TagService,
                "TeamInvitationService": TeamInvitationService,
                "TeamMemberService": TeamMemberService,
                "TeamService": TeamService,
                "UserOAuthAccountService": UserOAuthAccountService,
                "UserRoleService": UserRoleService,
                "UserService": UserService,
                "OffsetPagination": OffsetPagination,
            },
        )
        # dependencies
        dependencies = {"current_user": Provide(security.provide_user, sync_to_thread=False)}
        app_config.dependencies.update(dependencies)

        return app_config
