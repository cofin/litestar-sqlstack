"""Unit tests for exceptions module."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from litestar.exceptions import HTTPException, InternalServerException, PermissionDeniedException
from litestar.status_codes import HTTP_409_CONFLICT

from sqlstack.lib.exceptions import (
    ApplicationClientError,
    ApplicationError,
    AuthorizationError,
    HealthCheckConfigurationError,
    MissingDependencyError,
    _HTTPConflictException,
    after_exception_hook_handler,
    exception_to_http_response,
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
    """Test that ApplicationClientError inherits from ApplicationError."""
    error = ApplicationClientError("Client error")
    
    assert isinstance(error, ApplicationError)
    assert str(error) == "Client error"
    assert error.detail == "Client error"


def test_authorization_error_inheritance() -> None:
    """Test that AuthorizationError inherits from ApplicationClientError."""
    error = AuthorizationError("Access denied")
    
    assert isinstance(error, ApplicationClientError)
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


class TestAfterExceptionHookHandler:
    """Test after_exception_hook_handler function."""

    @patch("sqlstack.lib.exceptions.bind_contextvars")
    def test_application_error_ignored(self, mock_bind: MagicMock) -> None:
        """Test that ApplicationError is ignored by the hook."""
        error = ApplicationError("Test error")
        scope = {}
        
        after_exception_hook_handler(error, scope)
        
        mock_bind.assert_not_called()

    @patch("sqlstack.lib.exceptions.bind_contextvars")
    def test_http_client_error_ignored(self, mock_bind: MagicMock) -> None:
        """Test that HTTP client errors (4xx) are ignored."""
        error = HTTPException(detail="Not found", status_code=404)
        scope = {}
        
        after_exception_hook_handler(error, scope)
        
        mock_bind.assert_not_called()

    @patch("sqlstack.lib.exceptions.bind_contextvars")
    @patch("sys.exc_info")
    def test_server_error_logged(self, mock_exc_info: MagicMock, mock_bind: MagicMock) -> None:
        """Test that server errors (5xx) are logged."""
        mock_exc_info.return_value = ("type", "value", "traceback")
        error = HTTPException(detail="Internal error", status_code=500)
        scope = {}
        
        after_exception_hook_handler(error, scope)
        
        mock_bind.assert_called_once_with(exc_info=("type", "value", "traceback"))

    @patch("sqlstack.lib.exceptions.bind_contextvars")
    @patch("sys.exc_info")
    def test_generic_exception_logged(self, mock_exc_info: MagicMock, mock_bind: MagicMock) -> None:
        """Test that generic exceptions are logged."""
        mock_exc_info.return_value = ("type", "value", "traceback")
        error = ValueError("Generic error")
        scope = {}
        
        after_exception_hook_handler(error, scope)
        
        mock_bind.assert_called_once_with(exc_info=("type", "value", "traceback"))


class TestExceptionToHttpResponse:
    """Test exception_to_http_response function."""

    def test_authorization_error_mapping(self) -> None:
        """Test AuthorizationError maps to PermissionDeniedException."""
        mock_request = MagicMock()
        mock_request.app.debug = False
        error = AuthorizationError("Access denied")
        
        with patch("sqlstack.lib.exceptions.create_exception_response") as mock_create:
            exception_to_http_response(mock_request, error)
            
            args, kwargs = mock_create.call_args
            assert args[0] is mock_request
            assert isinstance(args[1], PermissionDeniedException)

    def test_generic_application_error_mapping(self) -> None:
        """Test generic ApplicationError maps to InternalServerException."""
        mock_request = MagicMock()
        mock_request.app.debug = False
        error = ApplicationError("Generic error")
        
        with patch("sqlstack.lib.exceptions.create_exception_response") as mock_create:
            exception_to_http_response(mock_request, error)
            
            args, kwargs = mock_create.call_args
            assert args[0] is mock_request
            assert isinstance(args[1], InternalServerException)

    def test_debug_mode_response(self) -> None:
        """Test debug mode returns debug response for server errors."""
        mock_request = MagicMock()
        mock_request.app.debug = True
        error = ApplicationError("Debug error")
        
        with patch("sqlstack.lib.exceptions.create_debug_response") as mock_debug:
            with patch("sqlstack.lib.exceptions.create_exception_response") as mock_exception:
                exception_to_http_response(mock_request, error)
                
                # Should call debug response for server errors in debug mode
                mock_debug.assert_called_once_with(mock_request, error)
                mock_exception.assert_not_called()

    def test_debug_mode_no_debug_for_permission_error(self) -> None:
        """Test debug mode doesn't show debug response for permission errors."""
        mock_request = MagicMock()
        mock_request.app.debug = True
        error = AuthorizationError("Permission denied")
        
        with patch("sqlstack.lib.exceptions.create_debug_response") as mock_debug:
            with patch("sqlstack.lib.exceptions.create_exception_response") as mock_exception:
                exception_to_http_response(mock_request, error)
                
                # Should not call debug response for permission errors even in debug mode
                mock_debug.assert_not_called()
                mock_exception.assert_called_once()

    def test_error_cause_in_detail(self) -> None:
        """Test that error cause is included in HTTP response detail."""
        mock_request = MagicMock()
        mock_request.app.debug = False
        
        # Create error with a cause
        original_error = ValueError("Original error")
        error = ApplicationError("Wrapper error")
        error.__cause__ = original_error
        
        with patch("sqlstack.lib.exceptions.create_exception_response") as mock_create:
            exception_to_http_response(mock_request, error)
            
            args, kwargs = mock_create.call_args
            http_exc = args[1]
            assert str(original_error) in http_exc.detail


class TestExceptionIntegration:
    """Test exception integration scenarios."""

    def test_exception_hierarchy(self) -> None:
        """Test that exception hierarchy is properly set up."""
        # Test inheritance chain
        assert issubclass(ApplicationClientError, ApplicationError)
        assert issubclass(AuthorizationError, ApplicationClientError)
        assert issubclass(AuthorizationError, ApplicationError)
        assert issubclass(MissingDependencyError, ApplicationError)
        assert issubclass(MissingDependencyError, ImportError)
        assert issubclass(HealthCheckConfigurationError, ApplicationError)

    def test_exception_with_chaining(self) -> None:
        """Test exception chaining works properly."""
        try:
            try:
                raise ValueError("Root cause")
            except ValueError as e:
                raise ApplicationError("Wrapped error") from e
        except ApplicationError as wrapper:
            assert wrapper.__cause__ is not None
            assert isinstance(wrapper.__cause__, ValueError)
            assert str(wrapper.__cause__) == "Root cause"

    def test_multiple_error_types(self) -> None:
        """Test different error types can be distinguished."""
        errors = [
            ApplicationError("Generic"),
            ApplicationClientError("Client"),
            AuthorizationError("Auth"),
            HealthCheckConfigurationError("Health"),
            MissingDependencyError("Dependency"),
        ]
        
        for error in errors:
            assert isinstance(error, ApplicationError)
            assert str(error) in repr(error)

    def test_error_detail_edge_cases(self) -> None:
        """Test edge cases in error detail handling."""
        # Empty string arguments should be filtered
        error1 = ApplicationError("", "Valid message", "")
        assert error1.detail == "Valid message"
        
        # All empty arguments
        error2 = ApplicationError("", "", "")
        assert error2.detail == ""
        
        # Mixed valid and invalid arguments
        error3 = ApplicationError("First", None, "Second", 0)  # 0 is falsy but valid
        assert error3.detail == "First"
        assert "Second" in str(error3)
        assert "0" in str(error3)