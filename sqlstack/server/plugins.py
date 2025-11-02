from litestar.plugins.problem_details import ProblemDetailsPlugin
from litestar.plugins.structlog import StructlogPlugin
from litestar_granian import GranianPlugin
from sqlspec.extensions.litestar import SQLSpecPlugin

from sqlstack import config
from sqlstack.server.worker_plugin import WorkerPlugin

structlog = StructlogPlugin(config=config.log)
sqlspec = SQLSpecPlugin(sqlspec=config.sqlspec)
granian = GranianPlugin()
problem_details = ProblemDetailsPlugin(config=config.problem_details)
worker = WorkerPlugin(start_worker=False, job_packages=["sqlstack.server.jobs"], auto_discover=True)
