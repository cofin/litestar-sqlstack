"""Application settings via environment variables."""

from __future__ import annotations

import binascii
import json
import os
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, cast
from urllib.parse import urlparse

from dotenv import load_dotenv
from litestar.data_extractors import RequestExtractorField
from litestar.utils.module_loader import module_to_os_path
from litestar_vite import PathConfig, RuntimeConfig, TypeGenConfig, ViteConfig
from sqlspec.adapters.asyncpg import AsyncpgConfig
from sqlspec.adapters.duckdb import DuckDBConfig
from sqlspec.utils.text import slugify

from sqlstack.__metadata__ import __version__ as current_version
from sqlstack.lib.exceptions import ConfigurationError
from sqlstack.utils.env import get_env

if TYPE_CHECKING:
    from collections.abc import Callable

    from litestar.data_extractors import ResponseExtractorField

DEFAULT_MODULE_NAME = "sqlstack"
BASE_DIR: Final[Path] = module_to_os_path(DEFAULT_MODULE_NAME)
TEMPLATE_DIR: Final[Path] = BASE_DIR / "server" / "templates"
STATIC_DIR = Path(BASE_DIR / "server" / "public")


def _get_sqlspec_log_level() -> int:
    """Get SQLSpec log level - DEBUG if ECHO enabled, else WARNING.

    When DATABASE_ECHO=True is set, SQLSpec's print_sql logs at DEBUG level.
    We auto-detect this and set the logger level accordingly so users don't need
    to configure two separate environment variables.

    Returns:
        Log level: DEBUG (10) if echo enabled or explicitly set, WARNING (30) otherwise.
    """
    # Allow explicit override
    explicit_level = os.getenv("SQLSPEC_LOG_LEVEL")
    if explicit_level:
        return int(explicit_level)

    # Auto-enable DEBUG when ECHO is enabled
    echo_enabled = os.getenv("DATABASE_ECHO", "").lower() in {"true", "1", "yes", "y", "t"}
    return 10 if echo_enabled else 30  # DEBUG=10, WARNING=30


@dataclass
class DatabaseSettings:
    """PostgreSQL database connection settings."""

    URL: str | None = field(default_factory=lambda: os.getenv("DATABASE_URL"))
    USER: str = field(default_factory=lambda: os.getenv("DATABASE_USER", "app"))
    PASSWORD: str = field(default_factory=lambda: os.getenv("DATABASE_PASSWORD", "super-secret"))
    HOST: str = field(default_factory=lambda: os.getenv("DATABASE_HOST", "localhost"))
    PORT: int = field(default_factory=lambda: int(os.getenv("DATABASE_PORT", "5432")))
    DATABASE: str = field(default_factory=lambda: os.getenv("DATABASE_NAME", "app"))
    POOL_MIN_SIZE: int = field(default_factory=lambda: int(os.getenv("DATABASE_POOL_MIN_SIZE", "5")))
    POOL_MAX_SIZE: int = field(default_factory=lambda: int(os.getenv("DATABASE_POOL_MAX_SIZE", "20")))
    POOL_TIMEOUT: int = field(default_factory=lambda: int(os.getenv("DATABASE_POOL_TIMEOUT", "30")))
    POOL_RECYCLE: int = field(default_factory=lambda: int(os.getenv("DATABASE_POOL_RECYCLE", "300")))
    ECHO: bool = field(default_factory=get_env("DATABASE_ECHO", False))
    """Print SQL statements to console for debugging."""
    MIGRATION_PATH: str = field(
        default_factory=get_env("DATABASE_MIGRATION_PATH", str(BASE_DIR / "db" / "migrations"))
    )
    """The path to database migrations."""
    MIGRATION_DDL_VERSION_TABLE: str = field(
        default_factory=get_env("DATABASE_MIGRATION_DDL_VERSION_TABLE", "ddl_version")
    )
    """The name to use for the migrations versions table name."""
    FIXTURE_PATH: str = field(default_factory=get_env("DATABASE_FIXTURE_PATH", str(BASE_DIR / "db" / "fixtures")))
    """The path to JSON fixture files to load into tables."""

    def get_connection_params(self) -> dict[str, Any]:
        """Extract connection parameters for PostgreSQL.

        If URL is provided, it takes precedence and individual params are ignored.
        """
        if self.URL:
            parsed = urlparse(self.URL)
            return {
                "user": parsed.username or "app",
                "password": parsed.password or "",
                "host": parsed.hostname or "localhost",
                "port": parsed.port or 5432,
                "database": parsed.path.lstrip("/") if parsed.path else "app",
            }
        return {
            "user": self.USER,
            "password": self.PASSWORD,
            "host": self.HOST,
            "port": self.PORT,
            "database": self.DATABASE,
        }

    def get_connection_string(self) -> str:
        """Get a PostgreSQL connection string for use with DuckDB's postgres extension."""
        params = self.get_connection_params()
        return (
            f"postgresql://{params['user']}:{params['password']}@{params['host']}:{params['port']}/{params['database']}"
        )

    def get_config(self) -> AsyncpgConfig:
        """Create PostgreSQL database configuration using asyncpg.

        Returns:
            AsyncpgConfig instance for database connection.
        """
        conn_params = self.get_connection_params()

        return AsyncpgConfig(
            connection_config={
                "user": conn_params["user"],
                "password": conn_params["password"],
                "host": conn_params["host"],
                "port": conn_params["port"],
                "database": conn_params["database"],
                "min_size": self.POOL_MIN_SIZE,
                "max_size": self.POOL_MAX_SIZE,
                "timeout": self.POOL_TIMEOUT,
                "command_timeout": 60,
                "max_queries": 50000,
                "max_inactive_connection_lifetime": float(self.POOL_RECYCLE),
            },
            migration_config={
                "version_table_name": self.MIGRATION_DDL_VERSION_TABLE,
                "script_location": self.MIGRATION_PATH,
                "project_root": BASE_DIR,
                "include_extensions": ["litestar"],
            },
            extension_config={"litestar": {"session_table": "app_session", "disable_di": True}},
        )


@dataclass
class ETLSettings:
    """DuckDB ETL database settings."""

    DATABASE_PATH: str | None = field(default_factory=get_env("ETL_DATABASE_PATH", None))
    """Database file path for DuckDB. Use ':memory:' for in-memory, None defaults to working_path/etl.db."""
    WORKING_PATH: str | None = field(default_factory=get_env("ETL_WORKING_PATH", None))
    """Working directory for DuckDB temp files. If None, uses system temp directory."""
    MAX_MEMORY: str | None = field(default_factory=get_env("ETL_MAX_MEMORY", None))
    """Maximum memory limit for DuckDB operations (e.g., '2GB', '500MB')."""
    MAX_TEMP_FILE_SIZE: str | None = field(default_factory=get_env("ETL_MAX_TEMP_FILE_SIZE", None))
    """Maximum size for DuckDB temporary files (e.g., '10GB')."""

    def get_working_path(self) -> Path:
        """Get working path for DuckDB, defaulting to temp directory if not configured."""
        import tempfile

        working_path = Path(self.WORKING_PATH) if self.WORKING_PATH else Path(tempfile.gettempdir()) / "sqlstack"
        working_path.mkdir(parents=True, exist_ok=True)
        return working_path

    def get_database_path(self) -> str:
        """Get database path, defaulting to working_path/etl.db if not configured."""
        if self.DATABASE_PATH:
            return self.DATABASE_PATH
        return str(self.get_working_path() / "etl.db")

    def get_connection_params(self) -> dict[str, Any]:
        """Get DuckDB connection parameters."""
        working_path = self.get_working_path()

        config: dict[str, Any] = {
            "database": self.get_database_path(),
            "temp_directory": str(working_path),
            "preserve_insertion_order": False,
            "extension_directory": str(working_path),
            "enable_object_cache": True,
        }
        if self.MAX_MEMORY:
            config["memory_limit"] = self.MAX_MEMORY
        if self.MAX_TEMP_FILE_SIZE:
            config["max_temp_directory_size"] = self.MAX_TEMP_FILE_SIZE
        return config

    def get_config(self, db_settings: DatabaseSettings | None = None) -> DuckDBConfig:
        """Create DuckDB configuration for ETL operations.

        Args:
            db_settings: Optional database settings to configure the postgres extension.
                        If provided, attaches the PostgreSQL database as 'pg' in DuckDB.
        """
        working_path = self.get_working_path()
        driver_features: dict[str, Any] = {}

        if db_settings is not None:
            pg_connection_string = db_settings.get_connection_string()
            driver_features["extensions"] = [{"name": "postgres"}]

            def on_connection_create(connection: Any) -> None:
                """Attach PostgreSQL database as 'pg' connection in DuckDB."""
                connection.execute(f"SET home_directory='{working_path}'")
                connection.execute(f"ATTACH '{pg_connection_string}' AS pg (TYPE POSTGRES)")

            driver_features["on_connection_create"] = on_connection_create

        return DuckDBConfig(
            connection_config=self.get_connection_params(),
            driver_features=driver_features or None,
            extension_config= {
                "litestar": {
                    "connection_key": "etl_connection",
                    "pool_key": "etl_pool",
                    "session_key": "etl_session",
                    "disable_di": True,
                }
            },
        )


@dataclass
class ViteSettings:
    """Vite build tool configurations."""

    DEV_MODE: bool = field(default_factory=get_env("VITE_DEV_MODE", False))
    """Start `vite` development server."""
    BUNDLE_DIR: Path = field(default_factory=get_env("VITE_BUNDLE_DIR", STATIC_DIR))
    """Bundle directory for built assets."""
    ASSET_URL: str = field(default_factory=get_env("ASSET_URL", "/static/"))
    """Base URL for assets."""
    TRUSTED_PROXIES: str | None = field(default_factory=get_env("LITESTAR_TRUSTED_PROXIES", None))
    """Trust X-Forwarded-* headers from these proxies. Use "*" to trust all."""

    def get_config(self, base_dir: Path = BASE_DIR.parent.parent) -> ViteConfig:
        js_home = base_dir / "js" / "web"
        return ViteConfig(
            mode="spa",
            dev_mode=self.DEV_MODE,
            runtime=RuntimeConfig(executor="bun", trusted_proxies=self.TRUSTED_PROXIES),
            paths=PathConfig(
                root=js_home,
                bundle_dir=self.BUNDLE_DIR,
                asset_url=self.ASSET_URL,
            ),
            types=TypeGenConfig(output=Path("src/lib/generated")),
        )


@dataclass
class AppSettings:
    """Application configuration."""

    NAME: str = field(default_factory=get_env("APP_NAME", "Litestar SQLStack"))
    VERSION: str = field(default=f"v{current_version}")
    URL: str = field(default_factory=get_env("APP_URL", "http://localhost:8000"))
    DEBUG: bool = field(default_factory=get_env("LITESTAR_DEBUG", False))
    SECRET_KEY: str = field(
        default_factory=get_env("SECRET_KEY", binascii.hexlify(os.urandom(32)).decode(encoding="utf-8"))
    )
    ALLOWED_CORS_ORIGINS: list[str] | str = field(default_factory=get_env("ALLOWED_CORS_ORIGINS", ["*"], list[str]))
    CSRF_COOKIE_NAME: str = field(default_factory=get_env("CSRF_COOKIE_NAME", "XSRF-TOKEN"))
    CSRF_HEADER_NAME: str = field(default_factory=get_env("CSRF_HEADER_NAME", "X-XSRF-TOKEN"))
    CSRF_COOKIE_SECURE: bool = field(default_factory=get_env("CSRF_COOKIE_SECURE", False))

    @property
    def slug(self) -> str:
        """Return a slugified name."""
        return slugify(self.NAME)

    def __post_init__(self) -> None:
        if isinstance(self.ALLOWED_CORS_ORIGINS, str):
            if self.ALLOWED_CORS_ORIGINS.startswith("[") and self.ALLOWED_CORS_ORIGINS.endswith("]"):
                try:
                    self.ALLOWED_CORS_ORIGINS = json.loads(self.ALLOWED_CORS_ORIGINS)  # pyright: ignore[reportConstantRedefinition]
                except (SyntaxError, ValueError):
                    msg = "ALLOWED_CORS_ORIGINS is not a valid list representation."
                    raise ValueError(msg) from None
            else:
                self.ALLOWED_CORS_ORIGINS = [host.strip() for host in self.ALLOWED_CORS_ORIGINS.split(",")]  # pyright: ignore[reportConstantRedefinition]


@dataclass
class LogSettings:
    """Logger configuration."""

    EXCLUDE_PATHS: str = field(
        default_factory=get_env(
            "LOG_EXCLUDE_PATHS",
            r"^/health|^/static/|^/assets/|^/@vite|^/@fs|^/node_modules|\.(?:js|css|ico|png|jpg|svg|woff2?)$",
        )
    )
    """Regex pattern for paths to exclude from logging."""
    INCLUDE_COMPRESSED_BODY: bool = False
    LEVEL: int = field(default_factory=get_env("LOG_LEVEL", 30))
    OBFUSCATE_COOKIES: set[str] = field(default_factory=lambda: {"session", "XSRF-TOKEN"})
    OBFUSCATE_HEADERS: set[str] = field(default_factory=lambda: {"Authorization", "X-API-KEY", "X-XSRF-TOKEN"})
    REQUEST_FIELDS: list[RequestExtractorField] = field(
        default_factory=get_env(
            "LOG_REQUEST_FIELDS", ["path", "method", "query", "path_params"], list[RequestExtractorField]
        )
    )
    RESPONSE_FIELDS: list[ResponseExtractorField] = field(
        default_factory=cast(
            "Callable[[],list[ResponseExtractorField]]", get_env("LOG_RESPONSE_FIELDS", ["status_code"])
        )
    )
    SQLSPEC_LEVEL: int = field(default_factory=_get_sqlspec_log_level)
    SQLGLOT_LEVEL: int = field(default_factory=get_env("SQLGLOT_LOG_LEVEL", 30))
    ASGI_ACCESS_LEVEL: int = field(default_factory=get_env("ASGI_ACCESS_LOG_LEVEL", 30))
    ASGI_ERROR_LEVEL: int = field(default_factory=get_env("ASGI_ERROR_LOG_LEVEL", 30))

    def create_structlog_config(self) -> Any:
        """Create the complete Litestar StructlogConfig.

        Returns:
            Configured StructlogConfig for Litestar application.
        """
        import logging

        import structlog
        from litestar.exceptions import NotAuthorizedException, PermissionDeniedException
        from litestar.logging.config import LoggingConfig, StructLoggingConfig, default_logger_factory
        from litestar.middleware.logging import LoggingMiddlewareConfig
        from litestar.plugins.structlog import StructlogConfig

        from sqlstack.lib import log as log_conf
        from sqlstack.lib.exceptions import (
            ClientError,
            ConflictError,
            NotFoundError,
            PasswordValidationError,
            ValidationError,
        )

        as_json = not log_conf.is_tty()
        disable_stack_trace: set[Any] = {
            400,
            401,
            403,
            404,
            409,
            ClientError,
            ConflictError,
            NotAuthorizedException,
            NotFoundError,
            PasswordValidationError,
            PermissionDeniedException,
            ValidationError,
        }

        return StructlogConfig(
            enable_middleware_logging=False,
            structlog_logging_config=StructLoggingConfig(
                log_exceptions="always",
                processors=log_conf.structlog_processors(as_json=as_json),
                logger_factory=default_logger_factory(as_json=as_json),
                disable_stack_trace=disable_stack_trace,
                standard_lib_logging_config=LoggingConfig(
                    log_exceptions="always",
                    disable_stack_trace=disable_stack_trace,
                    root={"level": logging.getLevelName(self.LEVEL), "handlers": ["queue_listener"]},
                    formatters= {
                        "standard": {
                            "()": structlog.stdlib.ProcessorFormatter,
                            "processors": log_conf.stdlib_logger_processors(as_json=as_json),
                        }
                    },
                    loggers= {
                        "sqlspec": {"propagate": False, "level": self.SQLSPEC_LEVEL, "handlers": ["queue_listener"]},
                        "sqlglot": {"propagate": False, "level": self.SQLGLOT_LEVEL, "handlers": ["queue_listener"]},
                        "_granian": {
                            "propagate": False,
                            "level": self.ASGI_ERROR_LEVEL,
                            "handlers": ["queue_listener"],
                        },
                        "granian.server": {
                            "propagate": False,
                            "level": self.ASGI_ERROR_LEVEL,
                            "handlers": ["queue_listener"],
                        },
                        "granian.access": {
                            "propagate": False,
                            "level": self.ASGI_ACCESS_LEVEL,
                            "handlers": ["queue_listener"],
                        },
                    },
                ),
            ),
            middleware_logging_config=LoggingMiddlewareConfig(
                request_log_fields=self.REQUEST_FIELDS, response_log_fields=self.RESPONSE_FIELDS
            ),
        )


@dataclass
class TaskSettings:
    """Task execution settings.

    Controls how background tasks are executed across different environments.
    """

    DEFAULT_EXECUTION_TARGET: Literal["local", "immediate"] = cast(
        'Literal["local", "immediate"]', field(default_factory=get_env("EXECUTION_TARGET", "local"))
    )
    """Default execution target for tasks.

    - local: Execute via local worker process (default for dev/prod)
    - immediate: Execute synchronously without database (for testing)
    """


@dataclass
class Settings:
    """Application settings container."""

    app: AppSettings = field(default_factory=AppSettings)
    db: DatabaseSettings = field(default_factory=DatabaseSettings)
    etl: ETLSettings = field(default_factory=ETLSettings)
    log: LogSettings = field(default_factory=LogSettings)
    task: TaskSettings = field(default_factory=TaskSettings)
    vite: ViteSettings = field(default_factory=ViteSettings)

    def ensure_directories(self) -> None:
        """Ensure required directories exist."""
        # Create ETL working directory
        self.etl.get_working_path().mkdir(parents=True, exist_ok=True)

        # Create template directory if it doesn't exist
        TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

    def setup_litestar_env(self) -> None:
        """Setup environment variables required by Litestar and granian."""
        os.environ.setdefault("LITESTAR_APP", "sqlstack.server.asgi:create_app")
        os.environ.setdefault("LITESTAR_APP_NAME", self.app.NAME)
        os.environ.setdefault("LITESTAR_GRANIAN_IN_SUBPROCESS", "false")
        os.environ.setdefault("LITESTAR_GRANIAN_USE_LITESTAR_LOGGER", "true")

    def get_config_value(self, key: str) -> Any:
        """Get configuration value by dot-notation key.

        Args:
            key: Configuration key (e.g., 'app.version', 'db.pool_max_size')

        Returns:
            Configuration value

        Raises:
            ConfigurationError: When key is not found
        """

        def _validate_key_format(key: str) -> tuple[str, str]:
            expected_parts = 2
            parts = key.split(".")
            if len(parts) != expected_parts:
                msg = "Key must be in format 'section.setting'"
                raise ValueError(msg)
            return parts[0], parts[1]

        try:
            section, setting = _validate_key_format(key)
            section_obj = getattr(self, section.lower())
            return getattr(section_obj, setting.upper())

        except (AttributeError, ValueError) as e:
            msg = f"Configuration key '{key}' not found"
            raise ConfigurationError(msg) from e

    def set_config_value(self, key: str, value: str) -> None:
        """Set configuration value by dot-notation key.

        Args:
            key: Configuration key (e.g., 'app.debug', 'db.pool_max_size')
            value: New value as string

        Raises:
            ConfigurationError: When key is invalid or value cannot be set
        """

        def _validate_set_key_format(key: str) -> tuple[str, str]:
            expected_parts = 2
            parts = key.split(".")
            if len(parts) != expected_parts:
                msg = "Key must be in format 'section.setting'"
                raise ValueError(msg)
            return parts[0], parts[1]

        try:
            section, setting = _validate_set_key_format(key)
            section_obj = getattr(self, section.lower())

            # Get current value to determine type
            current_value = getattr(section_obj, setting.upper())

            # Convert value to appropriate type
            if isinstance(current_value, bool):
                parsed_value: Any = value.lower() in {"true", "1", "yes", "on"}
            elif isinstance(current_value, int):
                parsed_value = int(value)
            elif isinstance(current_value, Path):
                parsed_value = Path(value)
            elif isinstance(current_value, list):
                parsed_value = [item.strip() for item in value.split(",")]
            else:
                parsed_value = value

            setattr(section_obj, setting.upper(), parsed_value)

        except (AttributeError, ValueError, TypeError) as e:
            msg = f"Cannot set configuration key '{key}' to '{value}': {e}"
            raise ConfigurationError(msg) from e

    def list_all_config(self) -> dict[str, dict[str, Any]]:
        """List all configuration settings by section.

        Returns:
            Dictionary with all configuration settings organized by section.
        """
        config: dict[str, dict[str, Any]] = {}

        for section_name in ("app", "db", "etl", "log", "task", "vite"):
            section_obj = getattr(self, section_name)
            section_config: dict[str, Any] = {}

            for attr_name in dir(section_obj):
                if not attr_name.startswith("_") and attr_name.isupper():
                    attr_value = getattr(section_obj, attr_name)
                    section_config[attr_name.lower()] = attr_value

            config[section_name] = section_config

        return config

    @classmethod
    @lru_cache(maxsize=1, typed=True)
    def from_env(cls, dotenv_filename: str = ".env") -> Settings:
        import structlog
        from litestar.cli._utils import console  # pyright: ignore[reportPrivateImportUsage]

        logger = structlog.get_logger()
        env_file = Path(f"{os.curdir}/{dotenv_filename}")
        env_file_exists = env_file.is_file()
        original_env = os.environ.copy()
        if env_file_exists:
            console.print(f"[yellow]Loading environment configuration from {dotenv_filename}[/]")
            load_dotenv(env_file, override=True)
        try:
            app = AppSettings()
            db = DatabaseSettings()
            etl = ETLSettings()
            log = LogSettings()
            task = TaskSettings()
            vite = ViteSettings()
        except Exception as e:  # noqa: BLE001
            logger.fatal("Could not load settings. %s", e)
            sys.exit(1)
        finally:
            os.environ.clear()
            os.environ.update(original_env)

        settings = Settings(app=app, db=db, etl=etl, log=log, task=task, vite=vite)

        # Setup Litestar environment variables early
        settings.setup_litestar_env()

        return settings


def get_settings(dotenv_filename: str = ".env") -> Settings:
    return Settings.from_env(dotenv_filename)
