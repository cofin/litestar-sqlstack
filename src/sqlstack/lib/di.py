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
    from litestar.connection import ASGIConnection

# Request context variables
query_id_var: ContextVar[str | None] = ContextVar("query_id", default=None)

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


__all__ = (
    "AsyncContainer",
    "Container",
    "Inject",
    "LitestarProvider",
    "LitestarRouter",
    "Provider",
    "QueryContext",
    "Scope",
    "get_from_connection",
    "inject",
    "make_async_container",
    "make_container",
    "provide",
    "query_id_var",
    "setup_dishka",
)
