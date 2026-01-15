"""Domain auto-discovery plugin for Litestar.

This plugin automatically discovers and registers controllers from domain packages,
eliminating the need for manual controller registration in ApplicationCore.

Discovery Pattern:
    The plugin scans domain packages (e.g., sqlstack.domain.*) for controller submodules:
    - controllers/ subpackage
    - routes/ subpackage
    - controller.py or controllers.py files
    - route.py or routes.py files

    Controllers are identified as subclasses of litestar.Controller defined in those modules.

Example:
    # In sqlstack/server/plugins.py
    from sqlstack.utils.domains import DomainPlugin, DomainPluginConfig

    domain = DomainPlugin(DomainPluginConfig(
        domain_packages=["sqlstack.domain"],
        discover_controllers=True,
        discover_jobs=True,
    ))

    # In ApplicationCore.on_app_init():
    app_config.plugins.append(plugins.domain)
"""

import contextlib
import importlib
import inspect
import pkgutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from litestar import Controller
from litestar.events import EventListener

from sqlstack.lib.di import LitestarRouter
from sqlstack.lib.jobs import discover_jobs

if TYPE_CHECKING:
    from litestar.config.app import AppConfig

logger = structlog.get_logger()


class _DiscoveryCache:
    """Cache for discovered controllers to avoid re-discovery."""

    def __init__(self) -> None:
        self.controllers: list[type[Controller]] | None = None
        self.packages: set[str] = set()

    def clear(self) -> None:
        """Clear the cache."""
        self.controllers = None
        self.packages.clear()

    def is_cached(self, domain_packages: list[str]) -> bool:
        """Check if results for these packages are cached."""
        return self.controllers is not None and frozenset(domain_packages) <= self.packages

    def get(self) -> list[type["Controller"]] | None:
        """Get cached controllers."""
        return self.controllers

    def set(self, controllers: list[type["Controller"]], packages: list[str]) -> None:
        """Set cached controllers."""
        self.controllers = controllers
        self.packages.update(packages)


_cache = _DiscoveryCache()


@dataclass
class DomainPluginConfig:
    """Configuration for domain auto-discovery plugin.

    Attributes:
        domain_packages: List of package paths containing domain subfolders.
            Each domain subfolder is scanned for controllers and jobs.
        discover_controllers: Whether to discover and register controllers.
        discover_jobs: Whether to discover and import job modules.
        controller_submodules: Module/package names to search for controllers.
        job_submodules: Module/package names to search for jobs.
        use_dishka_router: Whether to wrap controllers in LitestarRouter for DI.
        log_discovered: Whether to log discovered components at startup.
    """

    domain_packages: list[str] = field(default_factory=lambda: ["sqlstack.domain"])
    discover_controllers: bool = True
    discover_jobs: bool = True
    discover_listeners: bool = True
    controller_submodules: list[str] = field(default_factory=lambda: ["controllers", "routes", "controller", "route"])
    job_submodules: list[str] = field(default_factory=lambda: ["jobs"])
    listener_submodules: list[str] = field(default_factory=lambda: ["events", "listeners"])
    use_dishka_router: bool = True
    log_discovered: bool = True


def find_controllers_in_module(module: object) -> list[type["Controller"]]:
    """Find all Controller subclasses defined in a module.

    Only returns controllers that are defined in the module itself,
    not imported from elsewhere.

    Args:
        module: The module to inspect for controllers.

    Returns:
        List of Controller subclasses defined in the module.
    """
    controllers: list[type[Controller]] = []
    module_name = getattr(module, "__name__", "")

    for name, obj in inspect.getmembers(module, inspect.isclass):
        # Skip the Controller base class itself
        if obj is Controller:
            continue

        # Check if it's a Controller subclass
        if not issubclass(obj, Controller):
            continue

        # Only include controllers defined in this module (not imported)
        if getattr(obj, "__module__", None) != module_name:
            continue

        # Skip private classes
        if name.startswith("_"):
            continue

        controllers.append(obj)

    return controllers


def find_listeners_in_module(module: object) -> list[EventListener]:
    """Find all event listeners defined in a module.

    Args:
        module: The module to inspect for listeners.

    Returns:
        List of EventListener instances defined in the module.
    """
    listeners: list[EventListener] = []

    for _, obj in inspect.getmembers(module):
        if isinstance(obj, EventListener):
            listeners.append(obj)

    return listeners


def _iter_domain_directories(domain_pkg: str) -> list[tuple[str, Path]]:
    """Iterate through domain subdirectories in a package.

    Args:
        domain_pkg: The domain package path (e.g., "sqlstack.domain").

    Returns:
        List of (domain_module_path, domain_dir) tuples.
    """
    try:
        base_module = importlib.import_module(domain_pkg)
    except ImportError:
        logger.warning("Domain package not found", package=domain_pkg)
        return []

    if not hasattr(base_module, "__path__"):
        logger.warning("Package has no __path__", package=domain_pkg)
        return []

    base_path = Path(base_module.__path__[0])
    results: list[tuple[str, Path]] = []

    for domain_dir in sorted(base_path.iterdir()):
        if not domain_dir.is_dir():
            continue
        if domain_dir.name.startswith(("_", ".")):
            continue

        domain_module_path = f"{domain_pkg}.{domain_dir.name}"
        results.append((domain_module_path, domain_dir))

    return results


def _discover_controllers_in_submodule(controller_module_path: str) -> list[type["Controller"]]:
    """Discover controllers in a single submodule path.

    Args:
        controller_module_path: The full module path to search.

    Returns:
        List of discovered controllers.
    """
    try:
        controller_module = importlib.import_module(controller_module_path)
    except ImportError:
        return []

    all_controllers: list[type[Controller]] = []

    # If it's a package, walk through all modules in it
    if hasattr(controller_module, "__path__"):
        for _, modname, ispkg in pkgutil.walk_packages(controller_module.__path__, prefix=f"{controller_module_path}."):
            if ispkg:
                continue
            try:
                mod = importlib.import_module(modname)
                controllers = find_controllers_in_module(mod)
                all_controllers.extend(controllers)
            except (ImportError, AttributeError, SyntaxError) as e:
                logger.warning("Failed to import controller module", module=modname, error=str(e))

    # Also check the __init__.py of the package/module itself
    controllers = find_controllers_in_module(controller_module)
    all_controllers.extend(controllers)

    return all_controllers


def _discover_listeners_in_submodule(listener_module_path: str) -> list["EventListener"]:
    """Discover listeners in a single submodule path.

    Args:
        listener_module_path: The full module path to search.

    Returns:
        List of discovered listeners.
    """
    try:
        listener_module = importlib.import_module(listener_module_path)
    except ImportError:
        return []

    all_listeners: list[EventListener] = []

    # If it's a package, walk through all modules in it
    if hasattr(listener_module, "__path__"):
        for _, modname, ispkg in pkgutil.walk_packages(listener_module.__path__, prefix=f"{listener_module_path}."):
            if ispkg:
                continue
            try:
                mod = importlib.import_module(modname)
                listeners = find_listeners_in_module(mod)
                all_listeners.extend(listeners)
            except (ImportError, AttributeError, SyntaxError) as e:
                logger.warning("Failed to import listener module", module=modname, error=str(e))

    # Also check the __init__.py of the package/module itself
    listeners = find_listeners_in_module(listener_module)
    all_listeners.extend(listeners)

    return all_listeners


def discover_domain_controllers(
    domain_packages: list[str], controller_submodules: list[str] | None = None
) -> list[type["Controller"]]:
    """Discover controllers in domain subpackages.

    Scans each domain in domain_packages for controller submodules,
    imports all modules, and extracts Controller subclasses.

    Args:
        domain_packages: List of package paths (e.g., ["sqlstack.domain"]).
        controller_submodules: Module names to search for controllers.
            Defaults to ["controllers", "routes", "controller", "route"].

    Returns:
        List of discovered Controller subclasses.

    Example:
        controllers = discover_domain_controllers(["sqlstack.domain"])
        # Returns controllers from:
        # - sqlstack.domain.accounts.controllers
        # - sqlstack.domain.workspaces.controllers
        # - etc.
    """
    # Return cached results if available
    if _cache.is_cached(domain_packages):
        cached = _cache.get()
        if cached is not None:
            return cached

    if controller_submodules is None:
        controller_submodules = ["controllers", "routes", "controller", "route"]

    all_controllers: list[type[Controller]] = []

    for domain_pkg in domain_packages:
        for domain_module_path, _ in _iter_domain_directories(domain_pkg):
            for submodule_name in controller_submodules:
                controller_path = f"{domain_module_path}.{submodule_name}"
                controllers = _discover_controllers_in_submodule(controller_path)
                all_controllers.extend(controllers)

    # Deduplicate while preserving order
    seen: set[type[Controller]] = set()
    unique_controllers: list[type[Controller]] = []
    for ctrl in all_controllers:
        if ctrl not in seen:
            seen.add(ctrl)
            unique_controllers.append(ctrl)

    # Cache results
    _cache.set(unique_controllers, domain_packages)

    return unique_controllers


def discover_domain_jobs(domain_packages: list[str], job_submodules: list[str] | None = None) -> None:
    """Discover and import job modules from domain packages.

    Imports all job modules, triggering @register_job decorators
    to populate the global job registry.

    Args:
        domain_packages: List of package paths (e.g., ["sqlstack.domain"]).
        job_submodules: Module names to search for jobs.
            Defaults to ["jobs"].
    """
    if job_submodules is None:
        job_submodules = ["jobs"]

    for domain_pkg in domain_packages:
        for domain_module_path, _ in _iter_domain_directories(domain_pkg):
            for submodule_name in job_submodules:
                job_module_path = f"{domain_module_path}.{submodule_name}"
                with contextlib.suppress(ImportError):
                    discover_jobs(job_module_path)


def discover_domain_listeners(
    domain_packages: list[str], listener_submodules: list[str] | None = None
) -> list["EventListener"]:
    """Discover listeners in domain subpackages.

    Args:
        domain_packages: List of package paths.
        listener_submodules: Module names to search for listeners.

    Returns:
        List of discovered EventListener instances.
    """
    if listener_submodules is None:
        listener_submodules = ["events", "listeners"]

    all_listeners: list[EventListener] = []

    for domain_pkg in domain_packages:
        for domain_module_path, _ in _iter_domain_directories(domain_pkg):
            for submodule_name in listener_submodules:
                listener_path = f"{domain_module_path}.{submodule_name}"
                listeners = _discover_listeners_in_submodule(listener_path)
                all_listeners.extend(listeners)

    return all_listeners


class DomainPlugin:
    """Litestar plugin for automatic domain discovery.

    Discovers and registers:
    - Controller classes from domain.*.controllers/ (and similar patterns)
    - Job functions from domain.*.jobs/ (via existing @register_job decorators)
    - Event listeners from domain.*.events/ (via @listener decorator)

    This plugin implements Litestar's InitPluginProtocol to integrate with
    the application initialization lifecycle.

    Example:
        plugin = DomainPlugin(DomainPluginConfig(
            domain_packages=["sqlstack.domain"],
            discover_controllers=True,
            discover_jobs=True,
            discover_listeners=True,
        ))

        # In ApplicationCore:
        app_config.plugins.append(plugin)
    """

    __slots__ = ("config",)

    def __init__(self, config: DomainPluginConfig | None = None) -> None:
        """Initialize the domain plugin.

        Args:
            config: Plugin configuration. If None, uses defaults.
        """
        self.config = config or DomainPluginConfig()

    def on_app_init(self, app_config: "AppConfig") -> "AppConfig":
        """Initialize the plugin when app is created.

        This method is called by Litestar during application initialization.
        It discovers controllers and jobs based on the plugin configuration.

        Args:
            app_config: The Litestar application configuration.

        Returns:
            The modified application configuration.
        """
        if self.config.discover_controllers:
            self._discover_and_register_controllers(app_config)

        if self.config.discover_jobs:
            self._discover_domain_jobs()

        if self.config.discover_listeners:
            self._discover_and_register_listeners(app_config)

        return app_config

    def _discover_and_register_controllers(self, app_config: "AppConfig") -> None:
        """Discover controllers and register them with the application.

        Args:
            app_config: The Litestar application configuration.
        """
        controllers = discover_domain_controllers(self.config.domain_packages, self.config.controller_submodules)

        if not controllers:
            logger.warning("No controllers discovered", domain_packages=self.config.domain_packages)
            return

        if self.config.log_discovered:
            self._log_discovered_controllers(controllers)

        # Register controllers with Dishka router for DI support
        if self.config.use_dishka_router:
            router = LitestarRouter(path="/", route_handlers=controllers)
            app_config.route_handlers.append(router)
        else:
            app_config.route_handlers.extend(controllers)

    def _discover_and_register_listeners(self, app_config: "AppConfig") -> None:
        """Discover listeners and register them with the application.

        Args:
            app_config: The Litestar application configuration.
        """
        listeners = discover_domain_listeners(self.config.domain_packages, self.config.listener_submodules)

        if not listeners:
            return

        if self.config.log_discovered:
            logger.info(
                "Discovered domain listeners", total=len(listeners), domain_packages=self.config.domain_packages
            )

        app_config.listeners.extend(listeners)

    def _log_discovered_controllers(self, controllers: list[type["Controller"]]) -> None:
        """Log discovered controllers grouped by domain."""
        by_domain: dict[str, list[str]] = {}
        for ctrl in controllers:
            module = getattr(ctrl, "__module__", "unknown")
            parts = module.split(".")
            domain = parts[2] if len(parts) >= 3 and parts[1] == "domain" else "unknown"

            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(ctrl.__name__)

        logger.info(
            "Discovered domain controllers",
            total=len(controllers),
            by_domain={k: sorted(v) for k, v in sorted(by_domain.items())},
        )

    def _discover_domain_jobs(self) -> None:
        """Discover and import job modules from domains."""
        discover_domain_jobs(self.config.domain_packages, self.config.job_submodules)

        if self.config.log_discovered:
            logger.info("Domain job discovery complete", domain_packages=self.config.domain_packages)


def clear_discovery_cache() -> None:
    """Clear the controller discovery cache.

    Useful for testing or when domain structure changes at runtime.
    """
    _cache.clear()


__all__ = [
    "DomainPlugin",
    "DomainPluginConfig",
    "clear_discovery_cache",
    "discover_domain_controllers",
    "discover_domain_jobs",
    "find_controllers_in_module",
]
