"""User Account Controllers."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from litestar import Controller, delete, get, patch, post
from litestar.params import Parameter

from sqlstack import schemas as s
from sqlstack.lib.di import Inject, inject
from sqlstack.server import security
from sqlstack.services import OffsetPagination, TeamService


class TeamController(Controller):
    """Teams."""

    tags = ["Teams"]
    guards = [security.requires_active_user]
    signature_types = [TeamService, UUID, s, OffsetPagination]

    @get(component="team/list", operation_id="ListTeams", path="/api/teams")
    @inject
    async def list_teams(self, teams_service: Inject[TeamService], current_user: s.User) -> OffsetPagination[s.Team]:
        """List teams that your account can access.

        Args:
            teams_service: Team Service
            current_user: Current User

        Returns:
            OffsetPagination[s.Team]
        """
        return await teams_service.list_with_count(user=current_user)

    @post(operation_id="CreateTeam", path="/api/teams")
    @inject
    async def create_team(self, teams_service: Inject[TeamService], current_user: s.User, data: s.TeamCreate) -> s.Team:
        """Create a new team.

        Args:
            teams_service: Team Service
            current_user: Current User
            data: Team Create

        Returns:
            s.Team
        """
        # Add owner_id to the team creation data
        team_data = s.TeamCreate(
            name=data.name,
            description=data.description,
            slug=data.slug,
            owner_id=current_user.id,
            tags=data.tags if hasattr(data, "tags") else [],
        )
        return await teams_service.create(team_data)

    @get(operation_id="GetTeam", guards=[security.requires_team_membership], path="/api/teams/{team_id:uuid}")
    @inject
    async def get_team(
        self,
        teams_service: Inject[TeamService],
        team_id: Annotated[UUID, Parameter(title="Team ID", description="The team to retrieve.")],
    ) -> s.Team:
        """Get details about a team.

        Args:
            teams_service: Team Service
            team_id: Team ID

        Returns:
            s.Team
        """
        return await teams_service.get_one(team_id)

    @patch(operation_id="UpdateTeam", guards=[security.requires_team_admin], path="/api/teams/{team_id:uuid}")
    @inject
    async def update_team(
        self,
        data: s.TeamUpdate,
        teams_service: Inject[TeamService],
        team_id: Annotated[UUID, Parameter(title="Team ID", description="The team to update.")],
    ) -> s.Team:
        """Update a migration team.

        Args:
            data: Team Update
            teams_service: Team Service
            team_id: Team ID

        Returns:
            s.Team
        """
        return await teams_service.update(team_id, data)

    @delete(operation_id="DeleteTeam", guards=[security.requires_team_admin], path="/api/teams/{team_id:uuid}")
    @inject
    async def delete_team(
        self,
        teams_service: Inject[TeamService],
        team_id: Annotated[UUID, Parameter(title="Team ID", description="The team to delete.")],
    ) -> None:
        """Delete a team.

        Args:
            teams_service: Team Service
            team_id: Team ID
        """
        await teams_service.delete(team_id)
