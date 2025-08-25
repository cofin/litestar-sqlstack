from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from litestar import Controller, delete, get, patch, post
from litestar.di import Provide
from litestar.exceptions import HTTPException

from sqlstack.server import deps
from sqlstack.server.security import requires_active_user, requires_superuser

if TYPE_CHECKING:
    from uuid import UUID

    from litestar.params import Parameter

    from sqlstack import schemas as s
    from sqlstack.services import RoleService
    from sqlstack.services._base import OffsetPagination


class RoleController(Controller):
    """Handles the interactions within the Role objects."""

    path = "/api/roles"
    guards = [requires_active_user, requires_superuser]
    dependencies = {
        "roles_service": Provide(deps.provide_roles_service, sync_to_thread=False),
    }
    tags = ["Roles"]

    @get(operation_id="ListRoles")
    async def list_roles(
        self,
        roles_service: RoleService,
    ) -> OffsetPagination[s.Role]:
        """List roles.

        Args:
            roles_service: The role service.

        Returns:
            The list of roles.
        """
        return await roles_service.list_with_count()

    @get(operation_id="GetRole", path="/{role_id:uuid}")
    async def get_role(
        self,
        roles_service: RoleService,
        role_id: Annotated[UUID, Parameter(title="Role ID", description="The role to retrieve.")],
    ) -> s.Role:
        """Get a role.

        Args:
            role_id: The ID of the role to retrieve.
            roles_service: The role service.

        Returns:
            The role.
        """
        return await roles_service.get_one(role_id)

    @post(operation_id="CreateRole", path="/{role_id:uuid}")
    async def create_role(self, roles_service: RoleService, data: s.RoleCreate) -> s.Role:
        """Create a new role.

        Args:
            data: The data to create the role with.
            roles_service: The role service.

        Returns:
            The created role.
        """
        return await roles_service.create_role(data)

    @patch(operation_id="UpdateRole", path="/{role_id:uuid}")
    async def update_role(
        self,
        roles_service: RoleService,
        data: s.RoleUpdate,
        role_id: Annotated[UUID, Parameter(title="Role ID", description="The role to update.")],
    ) -> s.Role:
        """Update a role.

        Args:
            data: The data to update the role with.
            role_id: The ID of the role to update.
            roles_service: The role service.

        Raises:
            HTTPException: If the role is a default role.

        Returns:
            The updated role.
        """
        if hasattr(data, "name") and data.name in {"User", "Superuser"}:
            raise HTTPException(status_code=400, detail="Cannot update default roles")
        return await roles_service.update_role(role_id, data)

    @delete(operation_id="DeleteRole", path="/{role_id:uuid}")
    async def delete_role(
        self,
        roles_service: RoleService,
        role_id: Annotated[UUID, Parameter(title="Role ID", description="The role to delete.")],
    ) -> None:
        """Delete a tag.

        Args:
            role_id: The ID of the role to delete.
            roles_service: The role service.

        Raises:
            HTTPException: If the role is a default role.
        """
        role = await roles_service.get_one(role_id)
        if role.name in {"User", "Superuser"}:
            raise HTTPException(status_code=400, detail="Cannot delete default roles")
        await roles_service.delete(role_id)
