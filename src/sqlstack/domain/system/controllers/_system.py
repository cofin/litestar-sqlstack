from __future__ import annotations

from typing import Literal, TypeVar

import structlog
from litestar import Controller, MediaType, get
from litestar.response import Response

from sqlstack.domain.accounts.services import UserService
from sqlstack.domain.system import schemas as s
from sqlstack.lib.di import Inject, inject

logger = structlog.get_logger()
OnlineOffline = TypeVar("OnlineOffline", bound=Literal["online", "offline"])


class SystemController(Controller):
    tags = ["System"]
    signature_types = [UserService]

    @get(operation_id="SystemHealth", name="system:health", path="/health", summary="Health Check")
    @inject
    async def check_system_health(self, users_service: Inject[UserService]) -> Response[s.SystemHealth]:
        """Check database available and returns app config info.

        Args:
            users_service: The users service.

        Returns:
            The response object.
        """
        db_status: Literal["online", "offline"]
        try:
            _ = await users_service.driver.select_value_or_none("SELECT 1 as test")
            db_status = "online"
        except (ConnectionError, OSError):
            db_status = "offline"

        healthy = db_status == "online"
        if healthy:
            await logger.adebug("System Health", database_status=db_status)
        else:
            await logger.awarn("System Health Check", database_status=db_status)

        return Response(
            content=s.SystemHealth(database_status=db_status),
            status_code=200 if healthy else 500,
            media_type=MediaType.JSON,
        )
