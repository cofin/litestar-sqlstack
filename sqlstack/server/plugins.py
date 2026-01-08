from litestar.plugins.problem_details import ProblemDetailsPlugin
from litestar.plugins.structlog import StructlogPlugin
from litestar_granian import GranianPlugin
from litestar_vite import VitePlugin
from sqlspec.extensions.litestar import SQLSpecPlugin

from sqlstack import config
from sqlstack.domain.accounts.auth import OAuth2ProviderPlugin
from sqlstack.server.worker_plugin import WorkerPlugin
from sqlstack.utils.domains import DomainPlugin, DomainPluginConfig

structlog = StructlogPlugin(config=config.log)
sqlspec = SQLSpecPlugin(sqlspec=config.db_manager)
granian = GranianPlugin()
problem_details = ProblemDetailsPlugin(config=config.problem_details)
worker = WorkerPlugin(start_worker=False, auto_discover=True)
domain = DomainPlugin(
    DomainPluginConfig(
        domain_packages=["sqlstack.domain"],
        discover_controllers=True,
        discover_jobs=True,
    )
)
oauth2_provider = OAuth2ProviderPlugin()
vite = VitePlugin(config=config.vite)