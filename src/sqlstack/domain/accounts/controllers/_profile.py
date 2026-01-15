from __future__ import annotations

import structlog
from litestar import Controller, delete, get, patch

from sqlstack.domain.accounts import schemas as s  # noqa: TC001
from sqlstack.domain.accounts.security import requires_active_user
from sqlstack.domain.accounts.services import UserService
from sqlstack.lib.di import Inject, inject
from sqlstack.lib.schema import Message

logger = structlog.get_logger()


class ProfileController(Controller):
    """Handles the login and registration of the application."""

    tags = ["Access"]
    signature_types = [UserService]

    @get(
        operation_id="AccountProfile",
        path="/api/me",
        guards=[requires_active_user],
        summary="User Profile",
        description="User profile information.",
    )
    async def get_profile(self, current_user: s.User) -> s.User:
        """User profile.

        Returns:
            s.User: The current user's profile.
        """
        return current_user

    @patch(operation_id="AccountProfileUpdate", path="/api/me")
    @inject
    async def update_profile(
        self, current_user: s.User, data: s.ProfileUpdate, users_service: Inject[UserService]
    ) -> s.User:
        """User Profile.

        Args:
            current_user: The current user.
            data: The profile update data.
            users_service: The users service.

        Returns:
            The response object.
        """
        return await users_service.update_user(current_user.id, data)

    @patch(operation_id="AccountPasswordUpdate", path="/api/me/password")
    @inject
    async def update_password(
        self, current_user: s.User, data: s.PasswordUpdate, users_service: Inject[UserService]
    ) -> Message:
        """Update user password.

        Args:
            current_user: The current user.
            data: The password update data.
            users_service: The users service.

        Returns:
            The response object.
        """
        await users_service.update_password(current_user.id, data.current_password, data.new_password)
        return Message(message="Your password was successfully modified.")

    @delete(operation_id="AccountDelete", path="/profile/")
    @inject
    async def remove_account(self, current_user: s.User, users_service: Inject[UserService]) -> None:
        """Remove your account.

        Args:
            current_user: The current user.
            users_service: The users service.

        """
        await users_service.delete_user(current_user.id)
