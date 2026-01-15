"""User role routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from litestar import Controller, delete, post
from litestar.exceptions import HTTPException
from litestar.params import Parameter
from litestar.status_codes import HTTP_202_ACCEPTED, HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

from sqlstack.domain.accounts import security
from sqlstack.domain.accounts import schemas as s
from sqlstack.domain.accounts.services import RoleService, UserRoleService, UserService
from sqlstack.lib.di import Inject, inject
from sqlstack.lib.schema import Message


class UserRoleController(Controller):
    """Handles the adding and removing of User Role records."""

    path = "/api/user-roles"
    tags = ["User Roles"]
    guards = [security.requires_superuser]
    signature_types = [RoleService, UserRoleService, UserService, s, UUID]

    @post(operation_id="AssignUserRole")
    @inject
    async def assign_role(
        self,
        roles_service: Inject[RoleService],
        users_service: Inject[UserService],
        user_roles_service: Inject[UserRoleService],
        data: s.UserRoleCreate,
    ) -> s.UserRole:
        """Assign a role to a user."""

        user = await users_service.get_user(data.user_id)
        role = await roles_service.get_one(data.role_id)

        if await user_roles_service.user_has_role(data.user_id, data.role_id):
            msg = f"{user.email} already has the '{role.slug}' role"
            raise HTTPException(status_code=HTTP_409_CONFLICT, detail=msg)

        return await user_roles_service.assign_role_to_user(data.user_id, data.role_id)

    @delete(operation_id="RevokeUserRole", path="/{user_id:uuid}/{role_id:uuid}", status_code=HTTP_202_ACCEPTED)
    @inject
    async def revoke_role(
        self,
        users_service: Inject[UserService],
        user_roles_service: Inject[UserRoleService],
        roles_service: Inject[RoleService],
        user_id: Annotated[UUID, Parameter(title="User ID", description="The user to modify.")],
        role_id: Annotated[UUID, Parameter(title="Role ID", description="The role to revoke.")],
    ) -> Message:
        """Revoke a role from a user."""

        user = await users_service.get_user(user_id)
        role = await roles_service.get_one(role_id)

        if not await user_roles_service.user_has_role(user_id, role_id):
            msg = "role assignment not found"
            raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=msg)

        await user_roles_service.revoke_role_from_user(user_id, role_id)
        return Message(message=f"Removed the '{role.slug}' role from {user.email}.")
