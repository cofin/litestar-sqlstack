"""SQLStack exception types.

Also, defines functions that translate service and repository exceptions
into HTTP exceptions.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from litestar.exceptions import (
    HTTPException,
    InternalServerException,
    PermissionDeniedException,
)
from litestar.status_codes import HTTP_409_CONFLICT, HTTP_500_INTERNAL_SERVER_ERROR
from structlog.contextvars import bind_contextvars

if TYPE_CHECKING:
    from litestar.connection import Request
    from litestar.response import Response
    from litestar.types import Scope

__all__ = (
    "ApplicationClientError",
    "ApplicationError",
    "AuthorizationError",
    "HealthCheckConfigurationError",
    "MissingDependencyError",
    "after_exception_hook_handler",
)


class ApplicationError(Exception):
    """Base exception type for the application's custom exception types."""

    detail: str

    def __init__(self, *args: Any, detail: str = "") -> None:
        """Initialize ``ApplicationError``.

        Args:
            *args: args are converted to :class:`str` before passing to :class:`Exception`
            detail: detail of the exception.
        """
        str_args = [str(arg) for arg in args if arg]
        if not detail:
            if str_args:
                detail, *str_args = str_args
            elif hasattr(self, "detail"):
                detail = self.detail
        self.detail = detail
        super().__init__(*str_args)

    def __repr__(self) -> str:
        if self.detail:
            return f"{self.__class__.__name__} - {self.detail}"
        return self.__class__.__name__

    def __str__(self) -> str:
        return " ".join((*self.args, self.detail)).strip()


class MissingDependencyError(ApplicationError, ImportError):
    """Missing optional dependency.

    This exception is raised only when a module depends on a dependency that has not been installed.
    """


class ApplicationClientError(ApplicationError):
    """Base exception type for client errors."""


class AuthorizationError(ApplicationClientError):
    """A user tried to do something they shouldn't have."""


class HealthCheckConfigurationError(ApplicationError):
    """An error occurred while registering a health check."""


class _HTTPConflictException(HTTPException):
    """Request conflict with the current state of the target resource."""

    status_code = HTTP_409_CONFLICT


def after_exception_hook_handler(exc: Exception, _scope: Scope) -> None:
    """Binds `exc_info` key with exception instance as value to structlog
    context vars.

    This must be a coroutine so that it is not wrapped in a thread where we'll lose context.

    Args:
        exc: the exception that was raised.
        _scope: scope of the request
    """
    if isinstance(exc, ApplicationError):
        return
    if isinstance(exc, HTTPException) and exc.status_code < HTTP_500_INTERNAL_SERVER_ERROR:
        return
    bind_contextvars(exc_info=sys.exc_info())


def exception_to_http_response(
    request: Request[Any, Any, Any],
    exc: ApplicationError,
) -> Response[Any]:
    """Transform application exceptions to HTTP exceptions.

    Args:
        request: The request that experienced the exception.
        exc: Exception raised during handling of the request.

    Returns:
        Exception response appropriate to the type of original exception.
    """
    from litestar.exceptions.responses import create_debug_response, create_exception_response

    http_exc = PermissionDeniedException if isinstance(exc, AuthorizationError) else InternalServerException

    if request.app.debug and http_exc not in {PermissionDeniedException, AuthorizationError}:
        return create_debug_response(request, exc)
    return create_exception_response(request, http_exc(detail=str(exc.__cause__)))
