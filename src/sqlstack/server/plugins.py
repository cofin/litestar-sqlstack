"""Litestar server plugins registry.

Exposes server plugins with module-level __getattr__ for lazy loading.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from litestar.plugins import InitPluginProtocol

# Type annotations for module attributes to support type checkers
structlog: InitPluginProtocol
granian: InitPluginProtocol
sqlspec: InitPluginProtocol
db_plugin: InitPluginProtocol
problem_details: InitPluginProtocol
channels: InitPluginProtocol
worker: InitPluginProtocol
domain: InitPluginProtocol
vite: InitPluginProtocol
mcp: InitPluginProtocol
system_config: InitPluginProtocol

_initialized = False


def _initialize(force: bool = False) -> None:
    global _initialized
    if not force and _initialized:
        return

    from litestar.plugins.problem_details import ProblemDetailsPlugin
    from litestar.plugins.structlog import StructlogPlugin
    from litestar_granian import GranianPlugin
    from litestar_vite import VitePlugin
    from litestar_mcp import LitestarMCP, MCPConfig
    from sqlspec.extensions.litestar import SQLSpecPlugin

    from sqlstack import config
    from sqlstack.utils.domains import DomainPlugin, DomainPluginConfig
    from sqlstack.utils.system_config import SystemConfigPlugin
    from sqlstack.utils.worker import WorkerPlugin

    g = globals()
    g["structlog"] = StructlogPlugin(config=config.log)

    db_plugin_instance = SQLSpecPlugin(sqlspec=config.db_manager)
    g["db_plugin"] = db_plugin_instance
    g["sqlspec"] = db_plugin_instance

    g["granian"] = GranianPlugin()
    g["problem_details"] = ProblemDetailsPlugin(config=config.problem_details)
    g["channels"] = config.channels
    g["worker"] = WorkerPlugin(start_worker=False, auto_discover=True)
    g["domain"] = DomainPlugin(
        DomainPluginConfig(
            domain_packages=["sqlstack.domain"],
            discover_controllers=True,
            discover_jobs=True,
            discover_listeners=True,
            use_dishka_router=True,
            log_discovered=True,
        )
    )
    g["vite"] = VitePlugin(config=config.vite)
    g["mcp"] = LitestarMCP(config=MCPConfig(base_path="/mcp"))
    g["system_config"] = SystemConfigPlugin()

    _initialized = True


def __getattr__(name: str) -> Any:
    if name in {
        "structlog",
        "granian",
        "sqlspec",
        "db_plugin",
        "problem_details",
        "channels",
        "worker",
        "domain",
        "vite",
        "mcp",
        "system_config",
    }:
        if name not in globals():
            _initialize(force=True)
        return globals()[name]
    msg = f"module '{__name__}' has no attribute '{name}'"
    raise AttributeError(msg)


def _reset() -> None:
    global _initialized
    _initialized = False
    for name in (
        "structlog",
        "granian",
        "sqlspec",
        "db_plugin",
        "problem_details",
        "channels",
        "worker",
        "domain",
        "vite",
        "mcp",
        "system_config",
    ):
        if name in globals():
            del globals()[name]
