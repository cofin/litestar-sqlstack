"""Dependency injection utilities and request context.

This module provides a clean interface to the underlying DI framework
(Dishka) without exposing implementation details throughout the codebase,
plus request-scoped context variables for propagating data.

The clean naming pattern (`Inject` instead of `FromDishka`) improves
code readability and makes it easier to swap DI frameworks in the future.

Example:
    from sqlstack.lib.di import Inject, inject

    class MyController(Controller):
        @get("/")
        @inject
        async def handler(self, service: Inject[MyService]) -> Response:
            ...
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

from dishka import (  # pyright: ignore
    AsyncContainer,
    Container,
    Provider,
    Scope,
    make_async_container,
    make_container,
    provide,
)
from dishka.integrations.litestar import DishkaRouter as LitestarRouter
from dishka.integrations.litestar import FromDishka as Inject
from dishka.integrations.litestar import LitestarProvider, inject, setup_dishka

if TYPE_CHECKING:
    from litestar import WebSocket
    from litestar.connection import ASGIConnection

# Request context variables
query_id_var: ContextVar[str | None] = ContextVar("query_id", default=None)
request_container_var: ContextVar[AsyncContainer | None] = ContextVar("request_container", default=None)
worker_container_var: ContextVar[AsyncContainer | None] = ContextVar("worker_container", default=None)

T = TypeVar("T")


@dataclass
class QueryContext:
    """Request-scoped query context."""

    query_id: str


async def get_from_connection(  # noqa: UP047
    connection: ASGIConnection[Any, Any, Any, Any], dependency_type: type[T]
) -> T:
    """Get a dependency from the Dishka container via the connection.

    This is useful for code that runs outside of route handlers but still
    has access to the connection (e.g., auth callbacks, middleware).

    The Dishka middleware stores the request-scoped container in
    `connection.state.dishka_container`.

    Args:
        connection: The ASGI connection (Request or WebSocket).
        dependency_type: The type of dependency to retrieve (can be abstract).

    Returns:
        The resolved dependency instance.

    Example:
        ```python
        service = await get_from_connection(connection, UserService)
        user = await service.get_user(user_id)
        ```
    """
    container: AsyncContainer = connection.state.dishka_container
    return await container.get(dependency_type)


@asynccontextmanager
async def with_websocket_request(connection: "ASGIConnection[Any, Any, Any, Any]") -> AsyncIterator[AsyncContainer]:
    """Enter a temporary REQUEST scope for brief database operations.

    Dishka creates SESSION-scoped containers for WebSocket connections (long-lived),
    but services requiring DB connections are registered with REQUEST scope (short-lived).
    This creates a child REQUEST container to resolve these services.

    Args:
        connection: The ASGI connection (typically a WebSocket).

    Yields:
        A REQUEST-scoped container for resolving services.
    """
    session_container: AsyncContainer = connection.state.dishka_container
    async with session_container({}, scope=Scope.REQUEST) as request_container:
        yield request_container


@asynccontextmanager
async def worker_scope() -> AsyncIterator[AsyncContainer]:
    """Enter a temporary REQUEST scope using the worker container.

    Use this in background jobs to create short-lived database sessions
    instead of holding a session open for the entire job duration.
    """
    container = worker_container_var.get()
    if not container:
        msg = "No worker container found in context. Are you running in a worker?"
        raise RuntimeError(msg)

    async with container(scope=Scope.REQUEST) as request_container:
        yield request_container


class WebSocketScope:
    """Factory for creating short-lived REQUEST scopes in WebSocket handlers.

    Use as a Litestar dependency to get a callable that creates
    temporary REQUEST scopes for database operations.
    """

    def __init__(self, connection: "ASGIConnection[Any, Any, Any, Any]") -> None:
        self._connection = connection

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AsyncContainer]:
        async with with_websocket_request(self._connection) as container:
            yield container


def provide_websocket_scope(socket: "WebSocket") -> WebSocketScope:
    """Litestar dependency provider for WebSocketScope."""
    return WebSocketScope(socket)


__all__ = (
    "AsyncContainer",
    "Container",
    "Inject",
    "LitestarProvider",
    "LitestarRouter",
    "Provider",
    "QueryContext",
    "Scope",
    "WebSocketScope",
    "get_from_connection",
    "inject",
    "make_async_container",
    "make_container",
    "provide",
    "provide_websocket_scope",
    "query_id_var",
    "request_container_var",
    "setup_dishka",
    "with_websocket_request",
    "worker_container_var",
    "worker_scope",
)
