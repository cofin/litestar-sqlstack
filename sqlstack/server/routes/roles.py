from __future__ import annotations

from typing import Annotated
from uuid import UUID

from litestar import Controller, get
from litestar.params import Parameter

from sqlstack import schemas as s
from sqlstack.lib.di import Inject, inject
from sqlstack.server.security import requires_active_user, requires_superuser
from sqlstack.services import OffsetPagination, RoleService


class RoleController(Controller):
    """Handles the interactions within the Role objects."""

    path = "/api/roles"
    guards = [requires_active_user, requires_superuser]
    tags = ["Roles"]
    signature_types = [RoleService, s, UUID]

    @get(operation_id="ListRoles")
    @inject
    async def list_roles(self, roles_service: Inject[RoleService]) -> OffsetPagination[s.Role]:
        """List roles.

        Args:
            roles_service: The role service.

        Returns:
            The list of roles.
        """
        return await roles_service.list_with_count()

    @get(operation_id="GetRole", path="/{role_id:uuid}")
    @inject
    async def get_role(
        self,
        roles_service: Inject[RoleService],
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
