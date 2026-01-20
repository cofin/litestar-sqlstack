"""Background worker system.

This subpackage provides the background task worker system including:
- Worker: Core worker class that polls for and executes tasks
- WorkerPlugin: Litestar plugin for integrating the worker with the application

Example:
    from sqlstack.utils.worker import Worker, WorkerPlugin

    # Start worker standalone
    worker = Worker(poll_interval=3.0, batch_size=10)
    await worker.start()

    # Or integrate with Litestar
    app = Litestar(plugins=[WorkerPlugin(start_worker=True)])
"""

from sqlstack.utils.worker.plugin import WorkerPlugin
from sqlstack.utils.worker.worker import Worker

__all__ = ["Worker", "WorkerPlugin"]
