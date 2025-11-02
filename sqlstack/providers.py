"""Dishka providers for litestar-sqlstack.

This package defines the dependency injection graph for the application using
Dishka. It mirrors the multi-provider structure used in the oracle reference
implementation while remaining lightweight for the current SQLStack
architecture.

Providers
---------

``SQLSpecProvider``
    Manages SQLSpec configuration (APP scope) and REQUEST-scoped database sessions.
    The session provider wraps SQLSpec's `provide_session()` for automatic
    connection pooling and cleanup.

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

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide  # pyright: ignore
from sqlspec import SQLSpec
from sqlspec.adapters.asyncpg import AsyncpgConfig
from sqlspec.driver import AsyncDriverAdapterBase

from sqlstack.config import db_config, sqlspec
from sqlstack.lib.di import LitestarProvider, QueryContext, query_id_var
from sqlstack.services import EmailVerificationService, PasswordService, RoleService, UserRoleService, UserService

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
    """Provide SQLSpec configuration and database sessions.

    This provider handles the SQLSpec infrastructure:
    - SQLSpec manager (singleton, APP scope)
    - Database configuration (singleton, APP scope)
    - Database sessions (per-request, REQUEST scope)

    The session provider wraps SQLSpec's `provide_session()` context manager
    for automatic connection pooling and cleanup. Each HTTP request gets its
    own session which is automatically returned to the pool when the request
    completes.

    For CLI commands and background tasks that don't have a request context,
    use the manager and config directly:
        manager = await container.get(SQLSpec)
        config = await container.get(AsyncpgConfig)
        async with manager.provide_session(config) as session:
            # Your CLI/background task logic here
            pass
    """

    @provide(scope=Scope.APP)
    def get_sqlspec_manager(self) -> SQLSpec:
        """Provide SQLSpec manager singleton.

        The manager handles connection pooling and SQL file loading.
        Created once at application startup.
        """
        return sqlspec

    @provide(scope=Scope.APP)
    def get_database_config(self, manager: SQLSpec) -> AsyncpgConfig:
        """Provide database configuration singleton.

        Returns the database configuration.
        Created once at application startup.
        """
        return manager.get_config(db_config)

    @provide(scope=Scope.REQUEST)
    async def get_db_session(
        self,
        manager: SQLSpec,
        config: AsyncpgConfig,
    ) -> AsyncIterator[AsyncDriverAdapterBase]:
        """Provide SQLSpec async database session.

        This wraps SQLSpec's provide_session() context manager for
        automatic connection pooling and cleanup. Each HTTP request
        gets its own session which is automatically returned to the
        pool when the request completes.

        Args:
            manager: The SQLSpec manager (injected)
            config: The database config (injected)

        Yields:
            An async database driver session
        """
        async with manager.provide_session(config) as session:
            yield session


class CoreServiceProvider(Provider):
    """Provide core business services."""

    scope = Scope.REQUEST

    @provide
    def get_user_service(self, driver: AsyncDriverAdapterBase) -> UserService:
        return UserService(driver)

    @provide
    def get_role_service(self, driver: AsyncDriverAdapterBase) -> RoleService:
        return RoleService(driver)

    @provide
    def get_password_service(self, driver: AsyncDriverAdapterBase) -> PasswordService:
        return PasswordService(driver)

    @provide
    def get_email_verification_service(self, driver: AsyncDriverAdapterBase) -> EmailVerificationService:
        return EmailVerificationService(driver)

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
    """Construct the Dishka container used by the application.

    The container uses a single SQLSpecProvider with REQUEST-scoped sessions,
    matching the pattern from the Oracle reference implementation.

    Returns:
        Configured async container with all application providers.
    """

    return make_async_container(
        SQLSpecProvider(),
        CoreServiceProvider(),
        ContextProvider(),
        LitestarProvider(),
        skip_validation=True,
    )


__all__ = (
    "ContextProvider",
    "CoreServiceProvider",
    "SQLSpecProvider",
    "build_container",
    "get_request_container",
    "set_request_container",
)
