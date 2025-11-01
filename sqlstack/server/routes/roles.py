from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from litestar import Controller, get
from litestar.di import Provide

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
    dependencies = {"roles_service": Provide(deps.provide_role_service, sync_to_thread=False)}
    tags = ["Roles"]

    @get(operation_id="ListRoles")
    async def list_roles(self, roles_service: RoleService) -> OffsetPagination[s.Role]:
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
