"""User Account Controllers."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from litestar import Controller, delete, get, patch, post
from litestar.params import Dependency, Parameter
from sqlspec.extensions.litestar.providers import create_filter_dependencies

from sqlstack.domain.accounts import security
from sqlstack.domain.accounts import schemas as s
from sqlstack.domain.accounts.services import UserService
from sqlstack.lib.di import Inject, inject
from sqlstack.lib.service import FilterTypes, OffsetPagination


class UserController(Controller):
    """User Account Controller."""

    path = "/api/users"
    tags = ["User Accounts"]
    guards = [security.requires_superuser]
    signature_types = [UserService, s, FilterTypes, OffsetPagination]
    dependencies = create_filter_dependencies({
        "id_filter": UUID,
        "search": "name,email",
        "pagination_type": "limit_offset",
        "pagination_size": 20,
        "created_at": True,
        "updated_at": True,
        "sort_field": "name",
        "sort_order": "asc",
    })

    @get(operation_id="ListUsers")
    @inject
    async def list_users(
        self,
        users_service: Inject[UserService],
        filters: Annotated[list[FilterTypes], Dependency(skip_validation=True)],
    ) -> OffsetPagination[s.User]:
        """List users.

        Args:
            users_service: The user service.
            filters: The filters to apply.

        Returns:
            The list of users.
        """
        return await users_service.list_with_count(*filters)

    @get(operation_id="GetUser", path="/{user_id:uuid}")
    @inject
    async def get_user(
        self,
        users_service: Inject[UserService],
        user_id: Annotated[UUID, Parameter(title="User ID", description="The user to retrieve.")],
    ) -> s.User:
        """Get a user.

        Args:
            user_id: The ID of the user to retrieve.
            users_service: The user service.

        Returns:
            The user.
        """
        return await users_service.get_user(user_id)

    @post(operation_id="CreateUser")
    @inject
    async def create_user(self, users_service: Inject[UserService], data: s.UserCreate) -> s.User:
        """Create a new user.

        Args:
            data: The data to create the user with.
            users_service: The user service.

        Returns:
            The created user.
        """
        return await users_service.create_user(data)

    @patch(operation_id="UpdateUser", path="/{user_id:uuid}")
    @inject
    async def update_user(
        self,
        data: s.UserUpdate,
        users_service: Inject[UserService],
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
        return await users_service.update_user(user_id, data)

    @delete(operation_id="DeleteUser", path="/{user_id:uuid}")
    @inject
    async def delete_user(
        self,
        users_service: Inject[UserService],
        user_id: Annotated[UUID, Parameter(title="User ID", description="The user to delete.")],
    ) -> None:
        """Delete a user from the system.

        Args:
            user_id: The ID of the user to delete.
            users_service: The user service.
        """
        await users_service.delete_user(user_id)
