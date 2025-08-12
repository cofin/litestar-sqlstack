from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from litestar.events import listener

if TYPE_CHECKING:
    from uuid import UUID

logger = structlog.get_logger()


@listener("team_created")
async def team_created_event_handler(team_id: UUID) -> None:
    """Executes when a new team is created.

    Args:
        team_id: The primary key of the team that was created.
    """
    await logger.ainfo("Running post team creation flow.")
    # TODO: Implement with proper SQLSpec session management
    await logger.ainfo("Team created", team_id=team_id)
