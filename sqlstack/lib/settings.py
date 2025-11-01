"""All configuration via environment.

Take note of the environment variable prefixes required for each
settings class, except `AppSettings`.
"""

from __future__ import annotations

import binascii
import json
import os
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast
from urllib.parse import urlparse

from dotenv import load_dotenv
from litestar.data_extractors import RequestExtractorField
from litestar.utils.module_loader import module_to_os_path
from sqlspec.adapters.asyncpg import AsyncpgConfig
from sqlspec.utils.text import slugify

from sqlstack.__metadata__ import __version__ as current_version
from sqlstack.utils.env import get_env

if TYPE_CHECKING:
    from collections.abc import Callable

    from litestar.data_extractors import ResponseExtractorField

DEFAULT_MODULE_NAME = "sqlstack"
BASE_DIR: Final[Path] = module_to_os_path(DEFAULT_MODULE_NAME)
STATIC_DIR = Path(BASE_DIR / "server" / "public")
TEMPLATE_DIR = Path(BASE_DIR / "server" / "templates")
TRUE_VALUES = {"True", "true", "1", "yes", "Y", "T"}


@dataclass
class DatabaseSettings:
    """PostgreSQL Database connection settings."""

    # Database URL (optional, for connection string)
    URL: str | None = field(default_factory=lambda: os.getenv("DATABASE_URL"))
    """PostgreSQL Database URL. Format: postgresql://user:password@host:port/database"""

    # Standard Database fields
    USER: str = field(default_factory=lambda: os.getenv("DATABASE_USER", "app"))
    """PostgreSQL Database User."""
    PASSWORD: str = field(default_factory=lambda: os.getenv("DATABASE_PASSWORD", "super-secret"))
    """PostgreSQL Database Password."""
    HOST: str = field(default_factory=lambda: os.getenv("DATABASE_HOST", "localhost"))
    """PostgreSQL Database Host."""
    PORT: int = field(default_factory=lambda: int(os.getenv("DATABASE_PORT", "5432")))
    """PostgreSQL Database Port."""
    DATABASE: str = field(default_factory=lambda: os.getenv("DATABASE_NAME", "app"))
    """PostgreSQL Database Name."""
    POOL_MIN_SIZE: int = field(default_factory=lambda: int(os.getenv("DATABASE_POOL_MIN_SIZE", "5")))
    """Minimum pool size."""
    POOL_MAX_SIZE: int = field(default_factory=lambda: int(os.getenv("DATABASE_POOL_MAX_SIZE", "20")))
    """Maximum pool size."""
    POOL_TIMEOUT: int = field(default_factory=lambda: int(os.getenv("DATABASE_POOL_TIMEOUT", "30")))
    """Pool timeout in seconds."""
    POOL_RECYCLE: int = field(default_factory=lambda: int(os.getenv("DATABASE_POOL_RECYCLE", "300")))
    """Pool recycle time in seconds."""
    MIGRATION_PATH: str = field(
        default_factory=lambda: os.getenv("DATABASE_MIGRATION_PATH", f"{BASE_DIR}/db/migrations")
    )
    """Database migration path."""
    FIXTURE_PATH: str = f"{BASE_DIR}/db/fixtures"
    """The path to JSON fixture files to load into tables."""

    def get_connection_params(self) -> dict[str, Any]:
        """Extract connection parameters for PostgreSQL."""
        if self.URL:
            parsed = urlparse(self.URL)
            return {
                "user": parsed.username or self.USER,
                "password": parsed.password or self.PASSWORD,
                "host": parsed.hostname or self.HOST,
                "port": parsed.port or self.PORT,
                "database": parsed.path.lstrip("/") if parsed.path else self.DATABASE,
            }
        return {
            "user": self.USER,
            "password": self.PASSWORD,
            "host": self.HOST,
            "port": self.PORT,
            "database": self.DATABASE,
        }

    def create_config(self) -> AsyncpgConfig:
        """Create PostgreSQL database configuration using asyncpg."""
        conn_params = self.get_connection_params()

        return AsyncpgConfig(
            pool_config={
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
                "version_table_name": "ddl_version",
                "script_location": self.MIGRATION_PATH,
                "project_root": BASE_DIR,
                "include_extensions": ["litestar"],
            },
            extension_config={"litestar": {"session_table": "app_session"}},
        )


@dataclass
class ServerSettings:
    """Server configurations."""

    APP_LOC: str = "sqlspec.server.asgi:app"
    """Path to app executable, or factory."""
    HOST: str = field(default_factory=lambda: os.getenv("LITESTAR_HOST", "0.0.0.0"))  # noqa: S104
    """Server network host."""
    PORT: int = field(default_factory=lambda: int(os.getenv("LITESTAR_PORT", "8000")))
    """Server port."""
    KEEPALIVE: int = field(default_factory=lambda: int(os.getenv("LITESTAR_KEEPALIVE", "65")))
    """Seconds to hold connections open (65 is > AWS lb idle timeout)."""
    RELOAD: bool = field(default_factory=lambda: os.getenv("LITESTAR_RELOAD", "False") in TRUE_VALUES)
    """Turn on hot reloading."""
    RELOAD_DIRS: list[str] = field(default_factory=lambda: [f"{BASE_DIR}"])
    """Directories to watch for reloading."""
    HTTP_WORKERS: int | None = field(
        default_factory=lambda: int(os.getenv("WEB_CONCURRENCY")) if os.getenv("WEB_CONCURRENCY") is not None else None  # type: ignore[arg-type]
    )
    """Number of HTTP Worker processes to be spawned by Uvicorn."""


@dataclass
class EmailSettings:
    """Email configuration"""

    ENABLED: bool = field(default_factory=get_env("EMAIL_ENABLED", False))
    """Whether email sending is enabled."""
    SMTP_HOST: str = field(default_factory=get_env("EMAIL_SMTP_HOST", "localhost"))
    """SMTP server hostname."""
    SMTP_PORT: int = field(default_factory=get_env("EMAIL_SMTP_PORT", 587, int))
    """SMTP server port."""
    SMTP_USER: str = field(default_factory=get_env("EMAIL_SMTP_USER", ""))
    """SMTP username."""
    SMTP_PASSWORD: str = field(default_factory=get_env("EMAIL_SMTP_PASSWORD", ""))
    """SMTP password."""
    USE_TLS: bool = field(default_factory=get_env("EMAIL_USE_TLS", True))
    """Use TLS for SMTP connection."""
    USE_SSL: bool = field(default_factory=get_env("EMAIL_USE_SSL", False))
    """Use SSL for SMTP connection."""
    FROM_EMAIL: str = field(default_factory=get_env("EMAIL_FROM_ADDRESS", "noreply@localhost"))
    """Default from email address."""
    FROM_NAME: str = field(default_factory=get_env("EMAIL_FROM_NAME", "Litestar App"))
    """Default from name."""
    TIMEOUT: int = field(default_factory=get_env("EMAIL_TIMEOUT", 30, int))
    """SMTP connection timeout in seconds."""


@dataclass
class AppSettings:
    """Application configuration"""

    NAME: str = field(default_factory=lambda: "Litestar SQLStack Template")
    """Application name."""
    VERSION: str = field(default=f"v{current_version}")
    """Current application"""
    CONTACT_NAME: str = field(default="Admin")
    """Application contact name"""
    CONTACT_EMAIL: str = field(default="admin@localhost")
    """Application contact email"""
    URL: str = field(default_factory=get_env("APP_URL", "http://localhost:8000"))
    """The frontend base URL"""
    DEBUG: bool = field(default_factory=get_env("LITESTAR_DEBUG", False))
    """Run `Litestar` with `debug=True`."""
    SECRET_KEY: str = field(
        default_factory=get_env("SECRET_KEY", binascii.hexlify(os.urandom(32)).decode(encoding="utf-8"))
    )
    """Application secret key."""
    JWT_ENCRYPTION_ALGORITHM: str = "HS256"
    """JWT Algorithm to use"""
    ALLOWED_CORS_ORIGINS: list[str] | str = field(default_factory=get_env("ALLOWED_CORS_ORIGINS", ["*"], list[str]))
    """Allowed CORS Origins"""
    CSRF_COOKIE_NAME: str = field(default_factory=get_env("CSRF_COOKIE_NAME", "XSRF-TOKEN"))
    """CSRF Cookie Name"""
    CSRF_HEADER_NAME: str = field(default_factory=get_env("CSRF_HEADER_NAME", "X-XSRF-TOKEN"))
    """CSRF Header Name"""
    CSRF_COOKIE_SECURE: bool = field(default_factory=get_env("CSRF_COOKIE_SECURE", False))
    """CSRF Secure Cookie"""
    STATIC_DIR: Path = field(default_factory=get_env("STATIC_DIR", STATIC_DIR))
    """Default URL where static assets are located."""
    STATIC_URL: str = field(default_factory=get_env("STATIC_URL", "/web/"))
    """URL Location for Static assets."""
    BASE_URL: str | None = None
    """Fully qualified path to optional use for URL generation."""
    DEV_MODE: bool = field(default_factory=get_env("DEV_MODE", False))
    """Toggle dev mode flag.  This can be used enable extra processes during development."""
    GOOGLE_OAUTH2_CLIENT_ID: str = field(default_factory=get_env("GOOGLE_OAUTH2_CLIENT_ID", ""))
    """Google Client ID"""
    GOOGLE_OAUTH2_CLIENT_SECRET: str = field(default_factory=get_env("GOOGLE_OAUTH2_CLIENT_SECRET", ""))
    """Google Client Secret"""
    ENV_SECRETS: str = field(default_factory=get_env("ENV_SECRETS", "runtime-secrets"))
    """Path to environment secrets."""

    @property
    def slug(self) -> str:
        """Return a slugified name.

        Returns:
            `self.NAME`, all lowercase and hyphens instead of spaces.
        """
        return slugify(self.NAME)

    def __post_init__(self) -> None:
        # Check if the ALLOWED_CORS_ORIGINS is a string.
        if isinstance(self.ALLOWED_CORS_ORIGINS, str):
            # Check if the string starts with "[" and ends with "]", indicating a list.
            if self.ALLOWED_CORS_ORIGINS.startswith("[") and self.ALLOWED_CORS_ORIGINS.endswith("]"):
                try:
                    # Safely evaluate the string as a Python list.
                    self.ALLOWED_CORS_ORIGINS = json.loads(self.ALLOWED_CORS_ORIGINS)  # pyright: ignore[reportConstantRedefinition]
                except (SyntaxError, ValueError):
                    # Handle potential errors if the string is not a valid Python literal.
                    msg = "ALLOWED_CORS_ORIGINS is not a valid list representation."
                    raise ValueError(msg) from None
            else:
                # Split the string by commas into a list if it is not meant to be a list representation.
                self.ALLOWED_CORS_ORIGINS = [host.strip() for host in self.ALLOWED_CORS_ORIGINS.split(",")]  # pyright: ignore[reportConstantRedefinition]


@dataclass
class LogSettings:
    """Logger configuration"""

    # https://stackoverflow.com/a/1845097/6560549
    EXCLUDE_PATHS: str = r"\A(?!x)x"
    """Regex to exclude paths from logging."""
    INCLUDE_COMPRESSED_BODY: bool = False
    """Include 'body' of compressed responses in log output."""
    LEVEL: int = field(default_factory=get_env("LOG_LEVEL", 30))
    """Stdlib log levels.

    Only emit logs at this level, or higher.
    """
    OBFUSCATE_COOKIES: set[str] = field(default_factory=lambda: {"session", "XSRF-TOKEN"})
    """Request cookie keys to obfuscate."""
    OBFUSCATE_HEADERS: set[str] = field(default_factory=lambda: {"Authorization", "X-API-KEY", "X-XSRF-TOKEN"})
    """Request header keys to obfuscate."""
    REQUEST_FIELDS: list[RequestExtractorField] = field(
        default_factory=get_env(
            "LOG_REQUEST_FIELDS", ["path", "method", "query", "path_params"], list[RequestExtractorField]
        )
    )
    """Attributes of the [Request][litestar.connection.request.Request] to be
    logged."""
    RESPONSE_FIELDS: list[ResponseExtractorField] = field(
        default_factory=cast(
            "Callable[[],list[ResponseExtractorField]]", get_env("LOG_RESPONSE_FIELDS", ["status_code"])
        )
    )
    """Attributes of the [Response][litestar.response.Response] to be
    logged."""
    SQLSPEC_LEVEL: int = field(default_factory=get_env("SQLSPEC_LOG_LEVEL", 30))
    """Level to log SQLSpec logs."""
    SQLGLOT_LEVEL: int = field(default_factory=get_env("SQLGLOT_LOG_LEVEL", 30))
    """Level to log SQLGlot logs."""
    ASGI_ACCESS_LEVEL: int = field(default_factory=get_env("ASGI_ACCESS_LOG_LEVEL", 30))
    """Level to log uvicorn access logs."""
    ASGI_ERROR_LEVEL: int = field(default_factory=get_env("ASGI_ERROR_LOG_LEVEL", 30))
    """Level to log uvicorn error logs."""


@dataclass
class Settings:
    app: AppSettings = field(default_factory=AppSettings)
    db: DatabaseSettings = field(default_factory=DatabaseSettings)
    server: ServerSettings = field(default_factory=ServerSettings)
    log: LogSettings = field(default_factory=LogSettings)
    email: EmailSettings = field(default_factory=EmailSettings)

    @classmethod
    @lru_cache(maxsize=1, typed=True)
    def from_env(cls, dotenv_filename: str = ".env") -> Settings:
        import structlog
        from litestar.cli._utils import console  # pyright: ignore[reportPrivateImportUsage]

        logger = structlog.get_logger()
        _secret_id = os.environ.get("ENV_SECRETS", None)  # use this to load secrets in a container
        env_file = Path(f"{os.curdir}/{dotenv_filename}")
        env_file_exists = env_file.is_file()
        original_env = os.environ.copy()
        if env_file_exists:
            console.print(f"[yellow]Loading environment configuration from {dotenv_filename}[/]")
            load_dotenv(env_file, override=False)
        try:
            db: DatabaseSettings = DatabaseSettings()
            server: ServerSettings = ServerSettings()
            app: AppSettings = AppSettings()
            log: LogSettings = LogSettings()
            email: EmailSettings = EmailSettings()
        except Exception as e:  # noqa: BLE001
            logger.fatal("Could not load settings. %s", e)
            sys.exit(1)
        finally:
            os.environ.clear()
            os.environ.update(original_env)
        return Settings(app=app, db=db, server=server, log=log, email=email)


def get_settings(dotenv_filename: str = ".env") -> Settings:
    return Settings.from_env(dotenv_filename)
