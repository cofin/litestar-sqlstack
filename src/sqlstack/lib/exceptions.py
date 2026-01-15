"""SQLStack exception types and error handling utilities.

Defines application exception hierarchy and HTTP exception handlers
for converting service exceptions to HTTP responses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar.exceptions import HTTPException
from litestar.status_codes import HTTP_409_CONFLICT

if TYPE_CHECKING:
    from litestar.connection import Request
    from litestar.response import Response

__all__ = (
    "ApplicationError",
    "AuthorizationError",
    "ClientError",
    "ConfigurationError",
    "ConflictError",
    "DatabaseConnectionError",
    "HealthCheckConfigurationError",
    "MissingDependencyError",
    "NonRetryableError",
    "NotFoundError",
    "PasswordValidationError",
    "ValidationError",
    "_HTTPConflictException",
    "conflict_exception_handler",
    "not_found_exception_handler",
    "unique_violation_exception_handler",
    "validation_exception_handler",
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


class ConfigurationError(ApplicationError):
    """Configuration-related errors."""


class DatabaseConnectionError(ApplicationError):
    """Database connection and access errors."""


class MissingDependencyError(ApplicationError, ImportError):
    """Missing optional dependency.

    This exception is raised only when a module depends on a dependency that has not been installed.
    """


class HealthCheckConfigurationError(ApplicationError):
    """An error occurred while registering a health check."""


class NonRetryableError(ApplicationError):
    """Error that should not be retried by the worker.

    Raise this exception from a job function to indicate that the task
    should not be retried, regardless of the max_retries setting.

    Example:
        ```python
        @job
        async def process_payment(payment_id: str) -> None:
            payment = await get_payment(payment_id)
            if payment.status == "cancelled":
                raise NonRetryableError(
                    "Payment was cancelled by user"
                )
        ```
    """


class ClientError(ApplicationError):
    """Base exception type for client/user errors."""


class AuthorizationError(ClientError):
    """A user tried to do something they shouldn't have."""


class ValidationError(ClientError):
    """Data validation errors."""


class NotFoundError(ClientError):
    """Resource not found errors."""


class ConflictError(ClientError):
    """Resource conflict errors (e.g., duplicate key)."""


class PasswordValidationError(ValidationError):
    """Password validation errors."""


class _HTTPConflictException(HTTPException):
    """Request conflict with the current state of the target resource."""

    status_code = HTTP_409_CONFLICT


def validation_exception_handler(_request: Request[Any, Any, Any], exc: ValidationError) -> Response[Any]:
    """Convert ValidationError to HTTP 400 Bad Request response.

    Args:
        _request: The request that caused the exception (unused).
        exc: The validation exception.

    Returns:
        HTTP 400 response with error details.
    """
    from litestar.response import Response
    from litestar.status_codes import HTTP_400_BAD_REQUEST

    return Response(
        content={"detail": str(exc), "status_code": HTTP_400_BAD_REQUEST},
        status_code=HTTP_400_BAD_REQUEST,
        media_type="application/json",
    )


def not_found_exception_handler(_request: Request[Any, Any, Any], exc: NotFoundError) -> Response[Any]:
    """Convert NotFoundError to HTTP 404 Not Found response.

    Args:
        _request: The request that caused the exception (unused).
        exc: The not found exception.

    Returns:
        HTTP 404 response with error details.
    """
    from litestar.response import Response
    from litestar.status_codes import HTTP_404_NOT_FOUND

    return Response(
        content={"detail": str(exc), "status_code": HTTP_404_NOT_FOUND},
        status_code=HTTP_404_NOT_FOUND,
        media_type="application/json",
    )


def conflict_exception_handler(_request: Request[Any, Any, Any], exc: ConflictError) -> Response[Any]:
    """Convert ConflictError to HTTP 409 Conflict response.

    Args:
        _request: The request that caused the exception (unused).
        exc: The conflict exception.

    Returns:
        HTTP 409 response with error details.
    """
    from litestar.response import Response
    from litestar.status_codes import HTTP_409_CONFLICT

    return Response(
        content={"detail": str(exc), "status_code": HTTP_409_CONFLICT},
        status_code=HTTP_409_CONFLICT,
        media_type="application/json",
    )


def unique_violation_exception_handler(_request: Request[Any, Any, Any], _exc: Exception) -> Response[Any]:
    """Convert SQLSpec UniqueViolationError to HTTP 409 Conflict response.

    Args:
        _request: The request that caused the exception (unused).
        _exc: The unique violation exception from SQLSpec (unused).

    Returns:
        HTTP 409 response with error details.
    """
    from litestar.response import Response
    from litestar.status_codes import HTTP_409_CONFLICT

    return Response(
        content={"detail": "Resource already exists", "status_code": HTTP_409_CONFLICT},
        status_code=HTTP_409_CONFLICT,
        media_type="application/json",
    )
