"""Dishka providers for litestar-sqlstack.

This package defines the dependency injection graph for the application using
Dishka. It mirrors the multi-provider structure used in the DMA accelerator
reference implementation.

Providers
---------

``DomainServiceProvider``
    Constructs request-scoped business services using the database driver.

``LitestarPersistenceProvider``
    Provides database sessions for Litestar HTTP requests.

``CliPersistenceProvider``
    Provides database sessions for CLI commands.

``WorkerPersistenceProvider``
    Provides database sessions for background worker tasks.

``ContextProvider``
    Exposes request context utilities (``QueryContext``) so other subsystems
    can resolve them through DI when needed.

Container Factories
-------------------

``make_litestar_container()`` - For Litestar HTTP application
``make_cli_container()`` - For CLI commands
``make_worker_container()`` - For background worker tasks
"""

from collections.abc import AsyncIterator
from contextvars import ContextVar

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide  # pyright: ignore
from litestar import Litestar
from litestar.channels import ChannelsBackend
from sqlspec.driver import AsyncDriverAdapterBase

from sqlstack.config import db, db_manager
from sqlstack.domain.accounts.services import PasswordService, RoleService, UserRoleService, UserService
from sqlstack.domain.system.services import TaskService
from sqlstack.lib.di import LitestarProvider, QueryContext, query_id_var
from sqlstack.lib.realtime import RealtimePublisher

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


class DomainServiceProvider(Provider):
    """Provide domain/business services.

    All services are request-scoped and receive a database driver.
    """

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
    def get_user_role_service(self, driver: AsyncDriverAdapterBase) -> UserRoleService:
        return UserRoleService(driver)

    @provide
    def get_task_service(self, driver: AsyncDriverAdapterBase) -> TaskService:
        return TaskService(driver)

    @provide
    def provide_realtime_publisher(self, backend: "ChannelsBackend") -> RealtimePublisher:
        return RealtimePublisher(backend)


class LitestarPersistenceProvider(Provider):
    """Persistence provider for Litestar HTTP application.

    Provides database sessions from the connection pool for each request.
    """

    @provide(scope=Scope.REQUEST)
    async def provide_driver(self) -> AsyncIterator[AsyncDriverAdapterBase]:
        """Provide the database driver using a fresh session from the pool.

        This gets a fresh connection from the pool for each request,
        avoiding race conditions with Litestar's request lifecycle.

        Yields:
            AsyncDriverAdapterBase: Database driver session.
        """
        async with db_manager.provide_session(db) as driver:
            yield driver


class RealtimePersistenceProvider(Provider):
    """Persistence provider for Realtime Event System."""

    @provide(scope=Scope.APP)
    def provide_channels_backend(self, app: "Litestar") -> "ChannelsBackend":
        """Provide the ChannelsBackend from the Litestar application state.

        The backend is initialized by the ChannelsPlugin.
        """
        return app.channels


class WorkerRealtimePersistenceProvider(Provider):
    """Persistence provider for Realtime Event System in Worker context."""

    def __init__(self, backend: "ChannelsBackend") -> None:
        super().__init__()
        self._backend = backend

    @provide(scope=Scope.APP)
    def provide_channels_backend(self) -> "ChannelsBackend":
        """Provide the pre-initialized ChannelsBackend."""
        return self._backend


class CliPersistenceProvider(Provider):
    """Persistence provider for CLI commands.

    Provides database sessions for command-line operations.
    """

    @provide(scope=Scope.REQUEST)
    async def provide_driver(self) -> AsyncIterator[AsyncDriverAdapterBase]:
        """Provide the database driver using a fresh session.

        Yields:
            AsyncDriverAdapterBase: Database driver session.
        """
        async with db_manager.provide_session(db) as driver:
            yield driver


class WorkerPersistenceProvider(Provider):
    """Persistence provider for background worker tasks."""

    def __init__(self, worker_db: "AsyncpgConfig") -> None:
        super().__init__()
        self._worker_db = worker_db

    @provide(scope=Scope.REQUEST)
    async def provide_driver(self) -> AsyncIterator[AsyncDriverAdapterBase]:
        """Provide the database driver using a fresh session.

        Yields:
            AsyncDriverAdapterBase: Database driver session.
        """
        async with self._worker_db.provide_session() as driver:
            yield driver


class ContextProvider(Provider):
    """Provide request context utilities."""

    scope = Scope.REQUEST

    @provide
    def get_query_context(self) -> QueryContext | None:
        query_id = query_id_var.get()
        if not query_id:
            return None
        return QueryContext(query_id=query_id)


def make_litestar_container() -> AsyncContainer:
    """Create the Dishka container for Litestar HTTP application.

    Returns:
        Configured async container with Litestar providers.
    """
    return make_async_container(
        LitestarProvider(),
        LitestarPersistenceProvider(),
        RealtimePersistenceProvider(),
        DomainServiceProvider(),
        ContextProvider(),
        skip_validation=True,
    )


def make_cli_container() -> AsyncContainer:
    """Create the Dishka container for CLI commands.

    Returns:
        Configured async container for CLI use.
    """
    return make_async_container(CliPersistenceProvider(), DomainServiceProvider(), skip_validation=True)


def make_worker_container(worker_db: "AsyncpgConfig", backend: "ChannelsBackend") -> AsyncContainer:
    """Create the Dishka container for background worker.

    Returns:
        Configured async container for worker use.
    """
    return make_async_container(
        WorkerPersistenceProvider(worker_db),
        WorkerRealtimePersistenceProvider(backend),
        DomainServiceProvider(),
        skip_validation=True,
    )


__all__ = (
    "CliPersistenceProvider",
    "ContextProvider",
    "DomainServiceProvider",
    "LitestarPersistenceProvider",
    "RealtimePersistenceProvider",
    "WorkerPersistenceProvider",
    "WorkerRealtimePersistenceProvider",
    "get_request_container",
    "make_cli_container",
    "make_litestar_container",
    "make_worker_container",
    "set_request_container",
)
