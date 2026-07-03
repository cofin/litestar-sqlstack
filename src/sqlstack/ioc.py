"""Dishka providers for litestar-sqlstack.

This package defines the dependency injection graph for the application using
Dishka. It groups database, business service, and email providers under the
unified IoC class namespace.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextvars import ContextVar
from typing import TYPE_CHECKING

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide  # pyright: ignore
from litestar import Litestar
from litestar.channels import ChannelsBackend
from sqlspec.driver import AsyncDriverAdapterBase

from sqlstack.lib.di import LitestarProvider, QueryContext, query_id_var
from sqlstack.lib.realtime import RealtimePublisher

from litestar_email import EmailService
from sqlspec.adapters.asyncpg import AsyncpgConfig
from sqlstack.domain.accounts.services import PasswordService, RoleService, UserRoleService, UserService
from sqlstack.domain.system.services import InstallationService, SystemConfigService, TaskService
from sqlstack.lib.email import EmailMessageService


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


class IoC:
    """Namespace grouping all DI providers as nested classes."""

    class DB(Provider):
        """Database connectivity provider."""

        def __init__(
            self,
            worker_db: AsyncpgConfig | None = None,
            channels_backend: ChannelsBackend | None = None,
        ) -> None:
            super().__init__()
            self._worker_db = worker_db
            self._channels_backend = channels_backend

        @provide(scope=Scope.REQUEST)
        async def provide_driver(self) -> AsyncIterator[AsyncDriverAdapterBase]:
            """Provide the database driver using a fresh session."""
            from sqlstack.config import db, db_manager

            if self._worker_db is not None:
                async with self._worker_db.provide_session() as driver:
                    yield driver
            else:
                async with db_manager.provide_session(db) as driver:
                    yield driver

        @provide(scope=Scope.APP)
        def provide_channels_backend(self, app: Litestar | None = None) -> ChannelsBackend:
            """Provide the ChannelsBackend from construction or application state."""
            if self._channels_backend is not None:
                return self._channels_backend
            if app is not None:
                return app.channels
            raise RuntimeError("ChannelsBackend not configured")

    class Services(Provider):
        """Request-scoped business logic services provider."""

        scope = Scope.REQUEST

        @provide
        def get_user_service(self, driver: AsyncDriverAdapterBase) -> UserService:
            from sqlstack.domain.accounts.services import UserService

            return UserService(driver)

        @provide
        def get_role_service(self, driver: AsyncDriverAdapterBase) -> RoleService:
            from sqlstack.domain.accounts.services import RoleService

            return RoleService(driver)

        @provide
        def get_password_service(self, driver: AsyncDriverAdapterBase) -> PasswordService:
            from sqlstack.domain.accounts.services import PasswordService

            return PasswordService(driver)

        @provide
        def get_user_role_service(self, driver: AsyncDriverAdapterBase) -> UserRoleService:
            from sqlstack.domain.accounts.services import UserRoleService

            return UserRoleService(driver)

        @provide
        def get_task_service(self, driver: AsyncDriverAdapterBase) -> TaskService:
            from sqlstack.domain.system.services import TaskService

            return TaskService(driver)

        @provide
        def get_system_config_service(self, driver: AsyncDriverAdapterBase) -> SystemConfigService:
            from sqlstack.domain.system.services import SystemConfigService

            return SystemConfigService(driver)

        @provide
        def get_installation_service(self, driver: AsyncDriverAdapterBase) -> InstallationService:
            from sqlstack.domain.system.services import InstallationService

            return InstallationService(driver)

        @provide
        def provide_realtime_publisher(self, backend: ChannelsBackend) -> RealtimePublisher:
            return RealtimePublisher(backend)

        @provide
        def get_query_context(self) -> QueryContext | None:
            query_id = query_id_var.get()
            if not query_id:
                return None
            return QueryContext(query_id=query_id)

    class Email(Provider):
        """Transactional email tools provider."""

        @provide(scope=Scope.REQUEST)
        def provide_email_service(self) -> EmailService:
            from litestar_email import EmailConfig, EmailService, SMTPConfig
            from sqlstack.config import get_settings

            settings = get_settings()

            if not settings.email.ENABLED:
                config = EmailConfig(
                    backend="memory",
                    from_email=settings.email.FROM_EMAIL,
                )
            else:
                backend_config = SMTPConfig(
                    host=settings.email.SMTP_HOST,
                    port=settings.email.SMTP_PORT,
                    username=settings.email.SMTP_USER,
                    password=settings.email.SMTP_PASSWORD,
                    use_tls=settings.email.USE_TLS,
                    use_ssl=settings.email.USE_SSL,
                    timeout=settings.email.TIMEOUT,
                )
                config = EmailConfig(
                    backend="smtp",
                    backend_config=backend_config,
                    from_email=settings.email.FROM_EMAIL,
                )
            return EmailService(config)

        @provide(scope=Scope.REQUEST)
        def provide_email_message_service(self, email_service: EmailService) -> EmailMessageService:
            from sqlstack.lib.email import EmailMessageService

            return EmailMessageService(email_service)


def make_container(
    *,
    worker_db: AsyncpgConfig | None = None,
    litestar: bool = False,
    channels_backend: ChannelsBackend | None = None,
) -> AsyncContainer:
    """Create a configured async Dishka container.

    Args:
        worker_db: Optional db config for task worker context.
        litestar: Set True if resolving web/HTTP services.
        channels_backend: Optional pre-configured channels backend for background worker.

    Returns:
        AsyncContainer: configured container instance.
    """
    providers: list[Provider] = []
    if litestar:
        providers.append(LitestarProvider())
    providers.append(IoC.DB(worker_db=worker_db, channels_backend=channels_backend))
    providers.append(IoC.Services())
    providers.append(IoC.Email())
    return make_async_container(*providers, skip_validation=True)


# --- Backward Compatibility Helpers ---


def make_litestar_container() -> AsyncContainer:
    """Create container for Litestar web app."""
    return make_container(litestar=True)


def make_cli_container() -> AsyncContainer:
    """Create container for CLI execution."""
    return make_container()


def make_worker_container(worker_db: AsyncpgConfig, backend: ChannelsBackend) -> AsyncContainer:
    """Create container for task worker."""
    return make_container(worker_db=worker_db, channels_backend=backend)


__all__ = (
    "IoC",
    "get_request_container",
    "make_cli_container",
    "make_container",
    "make_litestar_container",
    "make_worker_container",
    "set_request_container",
)
