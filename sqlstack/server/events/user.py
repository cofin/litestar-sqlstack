from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from litestar.events import listener

if TYPE_CHECKING:
    from uuid import UUID

logger = structlog.get_logger()


@listener("user_created")
async def user_created_event_handler(user_id: UUID) -> None:
    """Executes when a new user is created.

    Args:
        user_id: The primary key of the user that was created.
    """
    await logger.ainfo("Running post signup flow.")
    # FIXME: Add user creation side effects (welcome email, default roles, etc.)
    # when SQLSpec session management is fully implemented
    await logger.ainfo("User created", user_id=user_id)
