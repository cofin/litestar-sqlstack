from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from litestar import Litestar


def create_app() -> Litestar:
    """Create ASGI application.

    Returns:
        The ASGI application.
    """
    from litestar import Litestar

    from sqlstack import config
    from sqlstack.lib.settings import get_settings
    from sqlstack.providers import build_container
    from sqlstack.server.core import ApplicationCore

    _ = config.log.structlog_logging_config.configure()()
    settings = get_settings()
    os.environ.setdefault("LITESTAR_APP", "sqlstack.server.asgi:app")
    os.environ.setdefault("LITESTAR_APP_NAME", settings.app.NAME)
    os.environ.setdefault("LITESTAR_GRANIAN_IN_SUBPROCESS", "false")
    os.environ.setdefault("LITESTAR_GRANIAN_USE_LITESTAR_LOGGER", "true")
    container = build_container()

    @asynccontextmanager
    async def dishka_lifespan(_app: Litestar) -> AsyncIterator[None]:
        """Manage Dishka container lifecycle."""
        yield
        await container.close()

    return Litestar(debug=settings.app.DEBUG, plugins=[ApplicationCore()], lifespan=[dishka_lifespan])


app = create_app()
