from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar.exceptions import PermissionDeniedException
from litestar.security.session_auth import SessionAuth

from sqlstack.config import db_manager, session_config
from sqlstack.domain.accounts import schemas as s
from sqlstack.domain.accounts.services import UserService
from sqlstack.server import plugins

if TYPE_CHECKING:
    from litestar.connection import ASGIConnection
    from litestar.handlers.base import BaseRouteHandler


def provide_user(request: ASGIConnection[Any, s.User, Any, Any]) -> s.User:
    """Get the user from the connection.

    Args:
        request: current connection.

    Returns:
        User
    """
    return request.user


def requires_active_user(connection: ASGIConnection[Any, s.User, Any, Any], _: BaseRouteHandler) -> None:
    """Request requires active user.

    Verifies the connection user is active.

    Args:
        connection (ASGIConnection): Request/Connection object.
        _ (BaseRouteHandler): Route handler.

    Raises:
        PermissionDeniedException: Not authorized
    """
    if connection.user.is_active:
        return
    msg = "Inactive account"
    raise PermissionDeniedException(msg)


def requires_verified_user(connection: ASGIConnection[Any, s.User, Any, Any], _: BaseRouteHandler) -> None:
    """Verify the connection user is verified.

    Args:
        connection (ASGIConnection): Request/Connection object.
        _ (BaseRouteHandler): Route handler.

    Raises:
        PermissionDeniedException: Not authorized
    """
    if connection.user.is_verified:
        return
    raise PermissionDeniedException(detail="User account is not verified.")


def requires_superuser(connection: ASGIConnection[Any, s.User, Any, Any], _: BaseRouteHandler) -> None:
    """Verify the connection user is a superuser.

    Args:
        connection (ASGIConnection): Request/Connection object.
        _ (BaseRouteHandler): Route handler.

    Raises:
        PermissionDeniedException: Not authorized
    """
    if any(
        assigned_role.role_name for assigned_role in connection.user.roles if assigned_role.role_slug == "superuser"
    ):
        return
    raise PermissionDeniedException(detail="Insufficient privileges")


async def retrieve_user_from_session(
    session: dict[str, Any], connection: ASGIConnection[Any, Any, Any, Any]
) -> s.User | None:
    """Retrieve user from session data.

    Fetches the user information from the database using the user_id stored in session.

    Args:
        session: Session data dictionary
        connection: ASGI connection

    Returns:
        User record or None if not found/inactive
    """
    user_id = session.get("user_id")
    if not user_id:
        return None

    driver = plugins.sqlspec.provide_async_request_session("db_session", connection.app.state, connection.scope)
    service = UserService(driver)
    user = await service.driver.select_one_or_none(
        db_manager.get_sql("get-user-account-details"), user_id=user_id, schema_type=s.User
    )
    return user if user and user.is_active else None


auth = SessionAuth[s.User, Any](
    retrieve_user_handler=retrieve_user_from_session,
    session_backend_config=session_config,
    exclude=["/health", "/api/health", "/api/access/login", "/api/access/signup", "^/schema", "^/public/"],
)
"""Session-based Authentication."""
