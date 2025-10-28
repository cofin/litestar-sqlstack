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
    # FIXME: Implement verification email sending when SQLSpec dependency injection is available  # noqa: FIX001
    # Need to inject EmailVerificationService and EmailService instances
    # verification_token = await verification_service.create_verification_token(user_id=user_id, email=user.email)  # noqa: ERA001
    # await email_service.send_verification_email(user, verification_token)  # noqa: ERA001
    await logger.ainfo("User created", user_id=user_id)
