"""Unit tests for exceptions module."""

from __future__ import annotations

from litestar.exceptions import HTTPException
from litestar.status_codes import HTTP_409_CONFLICT

from sqlstack.lib.exceptions import (
    ClientError,
    ApplicationError,
    AuthorizationError,
    HealthCheckConfigurationError,
    MissingDependencyError,
    _HTTPConflictException,
)


def test_basic_initialization() -> None:
    """Test basic error initialization."""
    error = ApplicationError("Test message")

    assert str(error) == "Test message"
    assert error.detail == "Test message"
    assert repr(error) == "ApplicationError - Test message"


def test_initialization_with_detail() -> None:
    """Test error initialization with explicit detail."""
    error = ApplicationError("Arg message", detail="Detail message")

    assert str(error) == "Arg message Detail message"
    assert error.detail == "Detail message"
    assert repr(error) == "ApplicationError - Detail message"


def test_initialization_multiple_args() -> None:
    """Test error with multiple arguments."""
    error = ApplicationError("First", "Second", "Third")

    assert error.detail == "First"
    assert str(error) == "Second Third First"


def test_initialization_empty_args() -> None:
    """Test error with empty arguments."""
    error = ApplicationError()

    assert error.detail == ""
    assert str(error) == ""
    assert repr(error) == "ApplicationError"


def test_initialization_with_none_args() -> None:
    """Test error filtering out None arguments."""
    error = ApplicationError("Valid", None, "Also valid", "")

    assert error.detail == "Valid"
    assert "None" not in str(error)


def test_predefined_detail_attribute() -> None:
    """Test error with predefined detail attribute."""

    class CustomError(ApplicationError):
        detail = "Custom detail"

    error = CustomError()
    assert error.detail == "Custom detail"
    assert repr(error) == "CustomError - Custom detail"


def test_application_client_error_inheritance() -> None:
    """Test that ClientError inherits from ApplicationError."""
    error = ClientError("Client error")

    assert isinstance(error, ApplicationError)
    assert str(error) == "Client error"
    assert error.detail == "Client error"


def test_authorization_error_inheritance() -> None:
    """Test that AuthorizationError inherits from ClientError."""
    error = AuthorizationError("Access denied")

    assert isinstance(error, ClientError)
    assert isinstance(error, ApplicationError)
    assert str(error) == "Access denied"


def test_health_check_configuration_error_inheritance() -> None:
    """Test that HealthCheckConfigurationError inherits from ApplicationError."""
    error = HealthCheckConfigurationError("Health check config error")

    assert isinstance(error, ApplicationError)
    assert str(error) == "Health check config error"


def test_missing_dependency_error_inheritance() -> None:
    """Test that MissingDependencyError inherits from both ApplicationError and ImportError."""
    error = MissingDependencyError("Missing dependency")

    assert isinstance(error, ApplicationError)
    assert isinstance(error, ImportError)
    assert str(error) == "Missing dependency"


def test_http_conflict_exception_status_code() -> None:
    """Test that _HTTPConflictException has correct status code."""
    error = _HTTPConflictException()

    assert isinstance(error, HTTPException)
    assert error.status_code == HTTP_409_CONFLICT


def test_exception_hierarchy() -> None:
    """Test that exception hierarchy is properly set up."""
    # Test inheritance chain
    assert issubclass(ClientError, ApplicationError)
    assert issubclass(AuthorizationError, ClientError)
    assert issubclass(AuthorizationError, ApplicationError)
    assert issubclass(MissingDependencyError, ApplicationError)
    assert issubclass(MissingDependencyError, ImportError)
    assert issubclass(HealthCheckConfigurationError, ApplicationError)


def test_exception_with_chaining() -> None:
    """Test exception chaining works properly."""
    try:
        try:
            msg = "Root cause"
            raise ValueError(msg)  # noqa: TRY301
        except ValueError as e:
            msg = "Wrapped error"
            raise ApplicationError(msg) from e
    except ApplicationError as wrapper:
        assert wrapper.__cause__ is not None
        assert isinstance(wrapper.__cause__, ValueError)
        assert str(wrapper.__cause__) == "Root cause"


def test_multiple_error_types() -> None:
    """Test different error types can be distinguished."""
    errors = [
        ApplicationError("Generic"),
        ClientError("Client"),
        AuthorizationError("Auth"),
        HealthCheckConfigurationError("Health"),
        MissingDependencyError("Dependency"),
    ]

    for error in errors:
        assert isinstance(error, ApplicationError)
        assert str(error) in repr(error)


def test_error_detail_edge_cases() -> None:
    """Test edge cases in error detail handling."""
    # Empty string arguments should be filtered
    error1 = ApplicationError("", "Valid message", "")
    assert error1.detail == "Valid message"

    # All empty arguments
    error2 = ApplicationError("", "", "")
    assert error2.detail == ""

    # Mixed valid and invalid arguments
    # Note: 0 is falsy and will be filtered out by the `if arg` check
    error3 = ApplicationError("First", None, "Second", 1)  # 1 is truthy
    assert error3.detail == "First"
    assert "Second" in str(error3)
    assert "1" in str(error3)
