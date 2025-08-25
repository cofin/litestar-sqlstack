from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from litestar import Controller, delete, get, patch
from litestar.di import Provide

from sqlstack import schemas as s
from sqlstack.server import deps
from sqlstack.server.security import requires_active_user

if TYPE_CHECKING:
    from sqlstack.services import UserService

logger = structlog.get_logger()


class ProfileController(Controller):
    """Handles the login and registration of the application."""

    tags = ["Access"]
    dependencies = {"users_service": Provide(deps.provide_users_service, sync_to_thread=False)}

    @get(
        operation_id="AccountProfile",
        path="/api/me",
        guards=[requires_active_user],
        summary="User Profile",
        description="User profile information.",
    )
    async def get_profile(self, users_service: UserService, current_user: s.User) -> s.User:
        """User profile.

        Returns:
            s.User: The current user's profile.
        """
        return current_user

    @patch(operation_id="AccountProfileUpdate", path="/api/me")
    async def update_profile(
        self,
        current_user: s.User,
        data: s.ProfileUpdate,
        users_service: UserService,
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
    async def update_password(
        self,
        current_user: s.User,
        data: s.PasswordUpdate,
        users_service: UserService,
    ) -> s.Message:
        """Update user password.

        Args:
            current_user: The current user.
            data: The password update data.
            users_service: The users service.

        Returns:
            The response object.
        """
        await users_service.update_password(current_user.id, data.new_password)
        return s.Message(message="Your password was successfully modified.")

    @delete(operation_id="AccountDelete", path="/profile/")
    async def remove_account(
        self,
        current_user: s.User,
        users_service: UserService,
    ) -> None:
        """Remove your account.

        Args:
            current_user: The current user.
            users_service: The users service.

        """
        await users_service.delete_user(current_user.id)
