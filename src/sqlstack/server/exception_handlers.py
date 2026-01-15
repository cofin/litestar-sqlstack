"""SQLStack exception types.

Also, defines functions that translate service and repository exceptions
into HTTP exceptions.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from litestar.exceptions import HTTPException, InternalServerException, PermissionDeniedException
from litestar.status_codes import HTTP_500_INTERNAL_SERVER_ERROR
from structlog.contextvars import bind_contextvars

from sqlstack.lib.exceptions import ApplicationError, AuthorizationError

if TYPE_CHECKING:
    from litestar.connection import Request
    from litestar.response import Response
    from litestar.types import Scope


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


def exception_to_http_response(request: Request[Any, Any, Any], exc: ApplicationError) -> Response[Any]:
    """Transform application exceptions to HTTP exceptions.

    Args:
        request: The request that experienced the exception.
        exc: Exception raised during handling of the request.

    Returns:
        Exception response appropriate to the type of original exception.
    """
    from litestar.exceptions.responses import (
        create_debug_response,  # pyright: ignore[reportUnknownVariableType]
        create_exception_response,  # pyright: ignore[reportUnknownVariableType]
    )

    http_exc = PermissionDeniedException if isinstance(exc, AuthorizationError) else InternalServerException

    if request.app.debug and http_exc not in {PermissionDeniedException, AuthorizationError}:
        return create_debug_response(request, exc)  # pyright: ignore[reportUnknownVariableType]
    return create_exception_response(request, http_exc(detail=str(exc.__cause__)))  # pyright: ignore[reportUnknownVariableType]
