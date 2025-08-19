from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypeVar

import structlog
from litestar import Controller, MediaType, get
from litestar.di import Provide
from litestar.response import Response

from sqlstack import schemas as s
from sqlstack.server import deps

if TYPE_CHECKING:
    from sqlstack.services._base import SQLSpecService

logger = structlog.get_logger()
OnlineOffline = TypeVar("OnlineOffline", bound=Literal["online", "offline"])


class SystemController(Controller):
    tags = ["System"]
    dependencies = {
        "users_service": Provide(deps.provide_users_service, sync_to_thread=False),
    }

    @get(
        operation_id="SystemHealth",
        name="system:health",
        path="/health",
        summary="Health Check",
    )
    async def check_system_health(self, users_service: SQLSpecService) -> Response[s.SystemHealth]:
        """Check database available and returns app config info.

        Args:
            users_service: The users service.

        Returns:
            The response object.
        """
        db_status: Literal["online", "offline"]
        try:
            # Test database connectivity via service driver
            await users_service.driver.select_one_or_none("SELECT 1 as test", schema_type=dict)
            db_status = "online"
        except (ConnectionError, OSError):
            db_status = "offline"

        healthy = db_status == "online"
        if healthy:
            await logger.adebug(
                "System Health",
                database_status=db_status,
            )
        else:
            await logger.awarn(
                "System Health Check",
                database_status=db_status,
            )

        return Response(
            content=s.SystemHealth(database_status=db_status),
            status_code=200 if healthy else 500,
            media_type=MediaType.JSON,
        )
