"""Dishka providers for litestar-sqlstack.

This package defines the dependency injection graph for the application using
Dishka. It mirrors the multi-provider structure used in the oracle reference
implementation while remaining lightweight for the current SQLStack
architecture.

Providers
---------

``SQLSpecProvider``
    Manages SQLSpec configuration and request-scoped database sessions,
    reusing the Litestar SQLSpec plugin when available.

``CoreServiceProvider``
    Constructs request-scoped business services using the database driver
    supplied by ``SQLSpecProvider``.

``ContextProvider``
    Exposes request context utilities (``QueryContext``) so other subsystems
    can resolve them through DI when needed.

``build_container()`` assembles these providers together with Dishka's
``LitestarProvider`` so the application can initialise the container during
startup and tear it down on shutdown.
"""

from collections.abc import AsyncIterator
from contextvars import ContextVar
from typing import Any

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide  # pyright: ignore
from litestar import Request
from sqlspec import SQLSpec
from sqlspec.adapters.asyncpg import AsyncpgConfig
from sqlspec.driver import AsyncDriverAdapterBase

from sqlstack.config import db_config, sqlspec
from sqlstack.lib.di import LitestarProvider, QueryContext, query_id_var
from sqlstack.services import (
    EmailVerificationService,
    PasswordService,
    RoleService,
    TagService,
    TeamMemberService,
    TeamService,
    UserRoleService,
    UserService,
)

_request_container: ContextVar[AsyncContainer | None] = ContextVar("_request_container", default=None)


def get_request_container() -> AsyncContainer:
    """Return the active request-scoped Dishka container.

    Returns:
        The active request container.

    Raises:
        RuntimeError: If called outside of a request lifecycle.
    """

    container = _request_container.get()
    if container is None:
        msg = "No active Dishka request container. Ensure DI middleware is configured."
        raise RuntimeError(msg)
    return container


def set_request_container(container: AsyncContainer | None) -> None:
    """Store the active request container in the context variable."""

    _request_container.set(container)


class SQLSpecProvider(Provider):
    """Provide SQLSpec configuration and request-scoped sessions."""

    scope = Scope.REQUEST

    @provide(scope=Scope.APP)
    def get_sqlspec_manager(self) -> SQLSpec:
        return sqlspec

    @provide(scope=Scope.APP)
    def get_database_config(self, manager: SQLSpec) -> AsyncpgConfig:
        return manager.get_config(db_config)

    @provide(scope=Scope.REQUEST)
    async def get_db_session(
        self, manager: SQLSpec, config: AsyncpgConfig, request: Request[Any, Any, Any] | None = None
    ) -> AsyncIterator[AsyncDriverAdapterBase]:
        if request is not None:
            from sqlstack.server import plugins

            driver = plugins.sqlspec.provide_async_request_session("db_session", request.app.state, request.scope)
            yield driver
            return

        async with manager.provide_session(config) as session:
            yield session


class CoreServiceProvider(Provider):
    """Provide core business services."""

    scope = Scope.REQUEST

    @provide
    def get_user_service(self, driver: AsyncDriverAdapterBase) -> UserService:
        return UserService(driver)

    @provide
    def get_team_service(self, driver: AsyncDriverAdapterBase) -> TeamService:
        return TeamService(driver)

    @provide
    def get_role_service(self, driver: AsyncDriverAdapterBase) -> RoleService:
        return RoleService(driver)

    @provide
    def get_tag_service(self, driver: AsyncDriverAdapterBase) -> TagService:
        return TagService(driver)

    @provide
    def get_password_service(self, driver: AsyncDriverAdapterBase) -> PasswordService:
        return PasswordService(driver)

    @provide
    def get_email_verification_service(self, driver: AsyncDriverAdapterBase) -> EmailVerificationService:
        return EmailVerificationService(driver)

    @provide
    def get_team_member_service(self, driver: AsyncDriverAdapterBase) -> TeamMemberService:
        return TeamMemberService(driver)

    @provide
    def get_user_role_service(self, driver: AsyncDriverAdapterBase) -> UserRoleService:
        return UserRoleService(driver)


class ContextProvider(Provider):
    """Provide request context utilities."""

    scope = Scope.REQUEST

    @provide
    def get_query_context(self) -> QueryContext | None:
        query_id = query_id_var.get()
        if not query_id:
            return None
        return QueryContext(query_id=query_id)


def build_container() -> AsyncContainer:
    """Construct the Dishka container used by the application."""

    return make_async_container(
        SQLSpecProvider(), CoreServiceProvider(), ContextProvider(), LitestarProvider(), skip_validation=True
    )


__all__ = (
    "ContextProvider",
    "CoreServiceProvider",
    "SQLSpecProvider",
    "build_container",
    "get_request_container",
    "set_request_container",
)
