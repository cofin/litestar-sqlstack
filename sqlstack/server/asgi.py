from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from litestar import Litestar


def create_app() -> Litestar:
    """Create ASGI application.

    Returns:
        The ASGI application.
    """
    from litestar import Litestar

    from sqlstack import config
    from sqlstack.lib.settings import get_settings
    from sqlstack.server.core import ApplicationCore

    _ = config.log.structlog_logging_config.configure()()
    settings = get_settings()
    os.environ.setdefault("LITESTAR_APP", "sqlstack.server.asgi:app")
    os.environ.setdefault("LITESTAR_APP_NAME", settings.app.NAME)
    os.environ.setdefault("LITESTAR_GRANIAN_IN_SUBPROCESS", "false")
    os.environ.setdefault("LITESTAR_GRANIAN_USE_LITESTAR_LOGGER", "true")

    return Litestar(plugins=[ApplicationCore()])


app = create_app()
