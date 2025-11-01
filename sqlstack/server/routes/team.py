"""Team management routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from litestar import Controller, delete, get, patch, post
from litestar.params import Dependency, Parameter
from sqlspec.extensions.litestar.providers import create_filter_dependencies

from sqlstack import schemas as s
from sqlstack.lib.di import Inject, inject
from sqlstack.server import security
from sqlstack.services import FilterTypes, OffsetPagination, TeamService


class TeamController(Controller):
    """Teams."""

    path = "/api/teams"
    tags = ["Teams"]
    guards = [security.requires_active_user]
    signature_types = [TeamService, s, FilterTypes, OffsetPagination, UUID]
    dependencies = create_filter_dependencies({
        "id_filter": UUID,
        "search": "name,description",
        "pagination_type": "limit_offset",
        "pagination_size": 20,
        "sort_field": "name",
        "sort_order": "asc",
        "created_at": True,
        "updated_at": True,
    })

    @get(operation_id="ListTeams")
    @inject
    async def list_teams(
        self,
        teams_service: Inject[TeamService],
        current_user: s.User,
        filters: Annotated[list[FilterTypes], Dependency(skip_validation=True)],
    ) -> OffsetPagination[s.Team]:
        """List teams the current user can access."""

        return await teams_service.list_teams(*filters, current_user=current_user)

    @post(operation_id="CreateTeam")
    @inject
    async def create_team(self, teams_service: Inject[TeamService], current_user: s.User, data: s.TeamCreate) -> s.Team:
        """Create a new team and assign the requester as owner."""

        return await teams_service.create_team(data, owner_id=current_user.id)

    @get(operation_id="GetTeam", path="/{team_id:uuid}", guards=[security.requires_team_membership])
    @inject
    async def get_team(
        self,
        teams_service: Inject[TeamService],
        team_id: Annotated[UUID, Parameter(title="Team ID", description="The team to retrieve.")],
    ) -> s.Team:
        """Return details for a specific team."""

        return await teams_service.get_team(team_id)

    @patch(operation_id="UpdateTeam", path="/{team_id:uuid}", guards=[security.requires_team_admin])
    @inject
    async def update_team(
        self,
        data: s.TeamUpdate,
        teams_service: Inject[TeamService],
        team_id: Annotated[UUID, Parameter(title="Team ID", description="The team to update.")],
    ) -> s.Team:
        """Update a team."""

        return await teams_service.update_team(team_id, data)

    @delete(operation_id="DeleteTeam", path="/{team_id:uuid}", guards=[security.requires_team_admin])
    @inject
    async def delete_team(
        self,
        teams_service: Inject[TeamService],
        team_id: Annotated[UUID, Parameter(title="Team ID", description="The team to delete.")],
    ) -> None:
        """Delete a team."""

        await teams_service.delete_team(team_id)
