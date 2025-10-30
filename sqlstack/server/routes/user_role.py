"""User Routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from litestar import Controller, delete, post
from litestar.di import Provide
from litestar.exceptions import HTTPException
from litestar.params import Parameter
from litestar.status_codes import HTTP_202_ACCEPTED

from sqlstack import schemas as s
from sqlstack.server import deps, security

if TYPE_CHECKING:
    from sqlstack.services import RoleService, UserRoleService, UserService


class UserRoleController(Controller):
    """Handles the adding and removing of User Role records."""

    tags = ["User Account Roles"]
    guards = [security.requires_superuser]
    dependencies = {
        "user_roles_service": Provide(deps.provide_user_role_service, sync_to_thread=False),
        "roles_service": Provide(deps.provide_role_service, sync_to_thread=False),
        "users_service": Provide(deps.provide_users_service, sync_to_thread=False),
    }

    @post(operation_id="AssignUserRole", path="/api/users/roles")
    async def assign_role(
        self,
        roles_service: RoleService,
        users_service: UserService,
        user_roles_service: UserRoleService,
        data: s.UserRoleAdd,
        role_slug: str = Parameter(title="Role Slug", description="The role to grant."),
    ) -> s.Message:
        """Create a new migration role.

        Args:
            roles_service: Role Service
            users_service: User Service
            user_roles_service: User Role Service
            data: User Role Add
            role_slug: Role Slug

        Returns:
            s.Message
        """
        role_id = (await roles_service.get_one(slug=role_slug)).id  # type: ignore[call-arg]
        user_obj = await users_service.get_user(email=data.user_name)  # type: ignore[call-arg]
        obj, created = await user_roles_service.get_or_upsert(role_id=role_id, user_id=user_obj.id)  # type: ignore[attr-defined]
        if created:
            return s.Message(message=f"Successfully assigned the '{obj.role_slug}' role to {obj.user_email}.")  # type: ignore[attr-defined]
        return s.Message(message=f"User {obj.user_email} already has the '{obj.role_slug}' role.")  # type: ignore[attr-defined]

    @delete(operation_id="RevokeUserRole", path="/api/users/roles", status_code=HTTP_202_ACCEPTED)
    async def revoke_role(
        self,
        users_service: UserService,
        user_roles_service: UserRoleService,
        data: s.UserRoleRevoke,
        role_slug: Annotated[str, Parameter(title="Role Slug", description="The role to revoke.")],
    ) -> s.Message:
        """Delete a role from the system.

        Args:
            users_service: User Service
            user_roles_service: User Role Service
            data: User Role Revoke
            role_slug: Role Slug

        Raises:
            IntegrityError: If the user does not have the role assigned.

        Returns:
            s.Message
        """
        user_obj = await users_service.get_user(email=data.user_name)  # type: ignore[call-arg]
        removed_role: bool = False
        for user_role in user_obj.roles:  # type: ignore[attr-defined]
            if user_role.role_slug == role_slug:  # type: ignore[attr-defined]
                _ = await user_roles_service.delete(user_role.id)  # type: ignore[attr-defined]
                removed_role = True
        if not removed_role:
            msg = "User did not have role assigned."
            raise HTTPException(status_code=400, detail=msg)
        return s.Message(message=f"Removed the '{role_slug}' role from User {user_obj.email}.")  # type: ignore[attr-defined]
