from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import structlog
from litestar.config.compression import CompressionConfig
from litestar.config.cors import CORSConfig
from litestar.config.csrf import CSRFConfig
from litestar.middleware.session.server_side import ServerSideSessionConfig
from litestar.plugins.problem_details import ProblemDetailsConfig
from litestar.stores.registry import StoreRegistry
from sqlspec import SQLSpec
from sqlspec.adapters.asyncpg.litestar.store import AsyncpgStore

from sqlstack.lib.settings import get_settings
from sqlstack.utils.env import BASE_DIR

if TYPE_CHECKING:
    from litestar.channels import ChannelsPlugin
    from litestar.plugins.structlog import StructlogConfig
    from litestar.stores.base import Store
    from litestar_vite import ViteConfig
    from sqlspec.adapters.asyncpg import AsyncpgConfig
    from sqlspec.adapters.duckdb import DuckDBConfig

DEFAULT_ACCESS_ROLE = "User"
"""The name of the default access role."""

SUPERUSER_ACCESS_ROLE = "Superuser"
"""The name of the superuser access role."""

# Type annotations for module attributes to support type checkers
compression: CompressionConfig
csrf: CSRFConfig
cors: CORSConfig
problem_details: ProblemDetailsConfig
vite: ViteConfig
db_manager: SQLSpec
db: AsyncpgConfig
etl_db: DuckDBConfig
channels: ChannelsPlugin
session_store: AsyncpgStore
stores: StoreRegistry
session_config: ServerSideSessionConfig
log: StructlogConfig

_initialized = False


def _initialize() -> None:
    global _initialized
    if _initialized:
        return

    _settings = get_settings()

    global compression, csrf, cors, problem_details, vite, db_manager, db, etl_db, channels, session_store, stores, session_config, log

    compression = CompressionConfig(backend="gzip")
    csrf = CSRFConfig(
        secret=_settings.app.SECRET_KEY,
        cookie_secure=_settings.app.CSRF_COOKIE_SECURE,
        cookie_name=_settings.app.CSRF_COOKIE_NAME,
        header_name=_settings.app.CSRF_HEADER_NAME,
    )
    cors = CORSConfig(allow_origins=cast("list[str]", _settings.app.ALLOWED_CORS_ORIGINS))
    problem_details = ProblemDetailsConfig(enable_for_all_http_exceptions=True)
    vite = _settings.vite.get_config()
    db_manager = SQLSpec()
    db = db_manager.add_config(_settings.db.get_config())
    etl_db = db_manager.add_config(_settings.etl.get_config(_settings.db))
    channels = _settings.channels.get_config()

    db_manager.load_sql_files(BASE_DIR / "sqlstack" / "db" / "sql")

    session_store = AsyncpgStore(config=db)
    stores = StoreRegistry(stores={"sessions": cast("Store", session_store)})
    session_config = ServerSideSessionConfig(store="sessions")

    log = _settings.log.create_structlog_config()

    _initialized = True


def __getattr__(name: str) -> Any:
    if name in {
        "compression",
        "csrf",
        "cors",
        "problem_details",
        "vite",
        "db_manager",
        "db",
        "etl_db",
        "channels",
        "session_store",
        "stores",
        "session_config",
        "log",
    }:
        _initialize()
        return globals()[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def _reset() -> None:
    global _initialized
    _initialized = False
    from sqlstack.lib.settings import Settings
    Settings.from_env.cache_clear()
    for name in {
        "compression",
        "csrf",
        "cors",
        "problem_details",
        "vite",
        "db_manager",
        "db",
        "etl_db",
        "channels",
        "session_store",
        "stores",
        "session_config",
        "log",
    }:
        if name in globals():
            del globals()[name]


def setup_logging() -> None:
    """Return a configured logger for the given name."""
    _initialize()
    if log.structlog_logging_config.standard_lib_logging_config:
        log.structlog_logging_config.standard_lib_logging_config.configure()
    log.structlog_logging_config.configure()
    structlog.configure(
        cache_logger_on_first_use=True,
        logger_factory=log.structlog_logging_config.logger_factory,
        processors=log.structlog_logging_config.processors,
        wrapper_class=structlog.make_filtering_bound_logger(get_settings().log.LEVEL),
    )
