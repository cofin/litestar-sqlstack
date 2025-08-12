"""Unit tests for settings module."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from sqlstack.lib.settings import (
    AppSettings,
    DatabaseSettings,
    EmailSettings,
    LogSettings,
    ServerSettings,
    Settings,
    StorageSettings,
    get_settings,
)


def test_database_settings_default_values() -> None:
    """Test default database settings values."""
    # Clear test environment to get actual defaults
    with patch.dict(os.environ, {}, clear=True):
        db_settings = DatabaseSettings()
        
        assert db_settings.ECHO is False
        assert db_settings.ECHO_POOL is False
        assert db_settings.POOL_DISABLED is False
        assert db_settings.POOL_MIN_SIZE == 1
        assert db_settings.POOL_MAX_SIZE == 10
        assert db_settings.POOL_TIMEOUT == 30
        assert db_settings.POOL_RECYCLE == 300
        assert db_settings.POOL_PRE_PING is False
        assert "postgres://app:app@localhost:15432/app" in db_settings.URL
        assert "migrations" in db_settings.MIGRATION_PATH
        assert db_settings.MIGRATION_DDL_VERSION_TABLE == "ddl_version"
        assert "fixtures" in db_settings.FIXTURE_PATH


def test_database_settings_env_override() -> None:
    """Test database settings environment variable overrides."""
    with patch.dict(os.environ, {
        "DATABASE_ECHO": "true",
        "DATABASE_POOL_MIN_SIZE": "5",
        "DATABASE_POOL_MAX_SIZE": "20",
        "DATABASE_URL": "postgres://test:test@localhost:5432/test",
    }):
        db_settings = DatabaseSettings()
        
        assert db_settings.ECHO is True
        assert db_settings.POOL_MIN_SIZE == 5
        assert db_settings.POOL_MAX_SIZE == 20
        assert db_settings.URL == "postgres://test:test@localhost:5432/test"


def test_server_settings_default_values() -> None:
    """Test default server settings."""
    server_settings = ServerSettings()
    
    assert server_settings.APP_LOC == "sqlstack.asgi:create_app"
    assert server_settings.HOST == "0.0.0.0"
    assert server_settings.PORT == 8000
    assert server_settings.KEEPALIVE == 65
    assert server_settings.RELOAD is False
    assert len(server_settings.RELOAD_DIRS) > 0


def test_server_settings_env_override() -> None:
    """Test server settings environment variable overrides."""
    with patch.dict(os.environ, {
        "LITESTAR_HOST": "127.0.0.1",
        "LITESTAR_PORT": "3000",
        "LITESTAR_RELOAD": "true",
    }):
        server_settings = ServerSettings()
        
        assert server_settings.HOST == "127.0.0.1"
        assert server_settings.PORT == 3000
        assert server_settings.RELOAD is True


def test_storage_settings_default_values() -> None:
    """Test default storage settings."""
    storage_settings = StorageSettings()
    
    assert storage_settings.PUBLIC_STORAGE_KEY == "public"
    assert storage_settings.PRIVATE_STORAGE_KEY == "private"
    assert "storage/public" in storage_settings.PUBLIC_STORAGE_URI
    assert "storage/private" in storage_settings.PRIVATE_STORAGE_URI
    assert isinstance(storage_settings.PUBLIC_STORAGE_OPTIONS, dict)
    assert isinstance(storage_settings.PRIVATE_STORAGE_OPTIONS, dict)


def test_storage_settings_env_override() -> None:
    """Test storage settings environment variable overrides."""
    with patch.dict(os.environ, {
        "PUBLIC_STORAGE_KEY": "assets",
        "PRIVATE_STORAGE_PATH_URI": "/tmp/private",
    }):
        storage_settings = StorageSettings()
        
        assert storage_settings.PUBLIC_STORAGE_KEY == "assets"
        assert storage_settings.PRIVATE_STORAGE_URI == "/tmp/private"


def test_email_settings_default_values() -> None:
    """Test default email settings."""
    email_settings = EmailSettings()
    
    assert email_settings.ENABLED is False
    assert email_settings.SMTP_HOST == "localhost"
    assert email_settings.SMTP_PORT == 587
    assert email_settings.SMTP_USER == ""
    assert email_settings.SMTP_PASSWORD == ""
    assert email_settings.USE_TLS is True
    assert email_settings.USE_SSL is False
    assert email_settings.FROM_EMAIL == "noreply@localhost"
    assert email_settings.FROM_NAME == "Litestar App"
    assert email_settings.TIMEOUT == 30


def test_email_settings_env_override() -> None:
    """Test email settings environment variable overrides."""
    with patch.dict(os.environ, {
        "EMAIL_ENABLED": "true",
        "EMAIL_SMTP_HOST": "smtp.example.com",
        "EMAIL_SMTP_PORT": "465",
        "EMAIL_USE_SSL": "true",
        "EMAIL_FROM_ADDRESS": "noreply@example.com",
    }):
        email_settings = EmailSettings()
        
        assert email_settings.ENABLED is True
        assert email_settings.SMTP_HOST == "smtp.example.com"
        assert email_settings.SMTP_PORT == 465
        assert email_settings.USE_SSL is True
        assert email_settings.FROM_EMAIL == "noreply@example.com"


def test_app_settings_default_values() -> None:
    """Test default app settings."""
    app_settings = AppSettings()
    
    assert "SQLStack" in app_settings.NAME
    assert app_settings.VERSION.startswith("v")
    assert app_settings.CONTACT_NAME == "Admin"
    assert app_settings.CONTACT_EMAIL == "admin@localhost"
    assert app_settings.URL == "http://localhost:8000"
    assert app_settings.DEBUG is False
    assert app_settings.JWT_ENCRYPTION_ALGORITHM == "HS256"
    assert isinstance(app_settings.ALLOWED_CORS_ORIGINS, list)
    assert app_settings.CSRF_COOKIE_NAME == "XSRF-TOKEN"
    assert app_settings.CSRF_HEADER_NAME == "X-XSRF-TOKEN"


def test_app_settings_slug_property() -> None:
    """Test slug generation from name."""
    app_settings = AppSettings()
    slug = app_settings.slug
    
    assert isinstance(slug, str)
    assert " " not in slug
    assert slug.lower() == slug


def test_app_settings_cors_origins_string_parsing() -> None:
    """Test CORS origins parsing from string."""
    # Test comma-separated string
    with patch.dict(os.environ, {
        "ALLOWED_CORS_ORIGINS": "http://localhost:3000,https://example.com"
    }):
        app_settings = AppSettings()
        assert app_settings.ALLOWED_CORS_ORIGINS == ["http://localhost:3000", "https://example.com"]


def test_app_settings_cors_origins_json_parsing() -> None:
    """Test CORS origins parsing from JSON string."""
    origins = ["http://localhost:3000", "https://example.com"]
    with patch.dict(os.environ, {
        "ALLOWED_CORS_ORIGINS": json.dumps(origins)
    }):
        app_settings = AppSettings()
        assert app_settings.ALLOWED_CORS_ORIGINS == origins


def test_app_settings_cors_origins_invalid_json() -> None:
    """Test invalid JSON raises ValueError."""
    with patch.dict(os.environ, {
        "ALLOWED_CORS_ORIGINS": "[invalid json"
    }):
        with pytest.raises(ValueError, match="ALLOWED_CORS_ORIGINS is not a valid list representation"):
            AppSettings()


def test_app_settings_env_override() -> None:
    """Test app settings environment variable overrides."""
    with patch.dict(os.environ, {
        "APP_URL": "https://example.com",
        "LITESTAR_DEBUG": "true",
        "SECRET_KEY": "test-secret",
        "GOOGLE_OAUTH2_CLIENT_ID": "test-client-id",
    }):
        app_settings = AppSettings()
        
        assert app_settings.URL == "https://example.com"
        assert app_settings.DEBUG is True
        assert app_settings.SECRET_KEY == "test-secret"
        assert app_settings.GOOGLE_OAUTH2_CLIENT_ID == "test-client-id"


def test_log_settings_default_values() -> None:
    """Test default log settings."""
    with patch.dict(os.environ, {}, clear=True):
        log_settings = LogSettings()
        
        assert log_settings.LEVEL == 30  # INFO
        assert log_settings.INCLUDE_COMPRESSED_BODY is False
        assert isinstance(log_settings.OBFUSCATE_COOKIES, set)
        assert isinstance(log_settings.OBFUSCATE_HEADERS, set)
        assert isinstance(log_settings.REQUEST_FIELDS, list)
        assert isinstance(log_settings.RESPONSE_FIELDS, list)
        assert log_settings.SQLSPEC_LEVEL == 30
        assert log_settings.ASGI_ACCESS_LEVEL == 30
        assert log_settings.ASGI_ERROR_LEVEL == 30


def test_log_settings_obfuscated_fields() -> None:
    """Test that sensitive fields are obfuscated."""
    log_settings = LogSettings()
    
    assert "session" in log_settings.OBFUSCATE_COOKIES
    assert "XSRF-TOKEN" in log_settings.OBFUSCATE_COOKIES
    assert "Authorization" in log_settings.OBFUSCATE_HEADERS
    assert "X-API-KEY" in log_settings.OBFUSCATE_HEADERS


def test_log_settings_env_override() -> None:
    """Test log settings environment variable overrides."""
    with patch.dict(os.environ, {
        "LOG_LEVEL": "10",  # DEBUG
        "SQLSPEC_LOG_LEVEL": "40",  # ERROR
    }):
        log_settings = LogSettings()
        
        assert log_settings.LEVEL == 10
        assert log_settings.SQLSPEC_LEVEL == 40


def test_settings_initialization() -> None:
    """Test settings initialization with defaults."""
    settings = Settings()
    
    assert isinstance(settings.app, AppSettings)
    assert isinstance(settings.db, DatabaseSettings)
    assert isinstance(settings.server, ServerSettings)
    assert isinstance(settings.log, LogSettings)
    assert isinstance(settings.storage, StorageSettings)
    assert isinstance(settings.email, EmailSettings)


def test_settings_from_env() -> None:
    """Test settings creation from environment."""
    with patch.dict(os.environ, {
        "SECRET_KEY": "test-from-env",
        "DATABASE_ECHO": "true",
    }):
        settings = Settings.from_env()
        
        assert settings.app.SECRET_KEY == "test-from-env"
        assert settings.db.ECHO is True


@patch("sqlstack.lib.settings.Path.is_file")
@patch("sqlstack.lib.settings.load_dotenv")
def test_settings_dotenv_loading(mock_load_dotenv, mock_is_file) -> None:
    """Test .env file loading."""
    mock_is_file.return_value = True
    
    Settings.from_env(".test.env")
    
    mock_load_dotenv.assert_called_once()


def test_get_settings_function() -> None:
    """Test get_settings convenience function."""
    settings = get_settings()
    
    assert isinstance(settings, Settings)
    assert isinstance(settings.app, AppSettings)


def test_settings_caching() -> None:
    """Test that settings are cached (lru_cache)."""
    settings1 = get_settings()
    settings2 = get_settings()
    
    # Should be the same instance due to lru_cache
    assert settings1 is settings2


def test_settings_exception_during_initialization() -> None:
    """Test system exit on settings initialization error."""
    with patch("sqlstack.lib.settings.DatabaseSettings", side_effect=Exception("Test error")):
        with pytest.raises(SystemExit):
            Settings.from_env()