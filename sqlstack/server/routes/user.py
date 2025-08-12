"""User Account Controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from litestar import Controller, delete, get, patch, post
from litestar.di import Provide
from litestar.params import Parameter

from sqlstack.server import deps, security

if TYPE_CHECKING:
    from uuid import UUID

    from sqlstack import schemas as s
    from sqlstack.services import UserService
    from sqlstack.services._base import OffsetPagination


class UserController(Controller):
    """User Account Controller."""

    path = "/api/users"
    tags = ["User Accounts"]
    guards = [security.requires_superuser]
    dependencies = {
        "users_service": Provide(deps.provide_users_service, sync_to_thread=False),
    }

    @get(operation_id="ListUsers")
    async def list_users(self, users_service: UserService) -> OffsetPagination[s.User]:
        """List users.

        Args:
            users_service: The user service.

        Returns:
            The list of users.
        """
        return await users_service.list_with_count()

    @get(operation_id="GetUser", path="/{user_id:uuid}")
    async def get_user(
        self,
        users_service: UserService,
        user_id: Annotated[UUID, Parameter(title="User ID", description="The user to retrieve.")],
    ) -> s.User:
        """Get a user.

        Args:
            user_id: The ID of the user to retrieve.
            users_service: The user service.

        Returns:
            The user.
        """
        return await users_service.get_one(user_id)

    @post(operation_id="CreateUser")
    async def create_user(self, users_service: UserService, data: s.UserCreate) -> s.User:
        """Create a new user.

        Args:
            data: The data to create the user with.
            users_service: The user service.

        Returns:
            The created user.
        """
        return await users_service.create(data)

    @patch(operation_id="UpdateUser", path="/{user_id:uuid}")
    async def update_user(
        self,
        data: s.UserUpdate,
        users_service: UserService,
        user_id: Annotated[UUID, Parameter(title="User ID", description="The user to update.")],
    ) -> s.User:
        """Update a user.

        Args:
            data: The data to update the user with.
            users_service: The user service.
            user_id: The ID of the user to update.

        Returns:
            The updated user.
        """
        return await users_service.update(user_id, data)

    @delete(operation_id="DeleteUser", path="/{user_id:uuid}")
    async def delete_user(
        self,
        users_service: UserService,
        user_id: Annotated[UUID, Parameter(title="User ID", description="The user to delete.")],
    ) -> None:
        """Delete a user from the system.

        Args:
            user_id: The ID of the user to delete.
            users_service: The user service.
        """
        await users_service.delete(user_id)
