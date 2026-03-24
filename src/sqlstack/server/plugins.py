from litestar.plugins.problem_details import ProblemDetailsPlugin
from litestar.plugins.structlog import StructlogPlugin
from litestar_granian import GranianPlugin
from litestar_vite import VitePlugin
from sqlspec.extensions.litestar import SQLSpecPlugin

from sqlstack import config
from sqlstack.utils.domains import DomainPlugin, DomainPluginConfig
from sqlstack.utils.worker import WorkerPlugin

structlog = StructlogPlugin(config=config.log)
sqlspec = SQLSpecPlugin(sqlspec=config.db_manager)
granian = GranianPlugin()
problem_details = ProblemDetailsPlugin(config=config.problem_details)
channels = config.channels
worker = WorkerPlugin(start_worker=False, auto_discover=True)
domain = DomainPlugin(
    DomainPluginConfig(
        domain_packages=["sqlstack.domain"],
        discover_controllers=True,
        discover_jobs=True,
        discover_listeners=True,
        use_dishka_router=True,
        log_discovered=True,
    )
)
vite = VitePlugin(config=config.vite)
