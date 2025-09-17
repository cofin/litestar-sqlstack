"""User Account Controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from litestar import Controller, delete, get, patch, post
from litestar.di import Provide

from sqlstack import schemas as s
from sqlstack.server import deps, security

if TYPE_CHECKING:
    from uuid import UUID

    from litestar.params import Parameter

    from sqlstack.services import TeamService
    from sqlstack.services._base import OffsetPagination


class TeamController(Controller):
    """Teams."""

    tags = ["Teams"]
    dependencies = {
        "teams_service": Provide(deps.provide_team_service, sync_to_thread=False),
    }

    guards = [security.requires_active_user]

    @get(component="team/list", operation_id="ListTeams", path="/api/teams")
    async def list_teams(
        self,
        teams_service: TeamService,
        current_user: s.User,
    ) -> OffsetPagination[s.Team]:
        """List teams that your account can access.

        Args:
            teams_service: Team Service
            current_user: Current User

        Returns:
            OffsetPagination[s.Team]
        """
        return await teams_service.list_with_count(user=current_user)

    @post(operation_id="CreateTeam", path="/api/teams")
    async def create_team(self, teams_service: TeamService, current_user: s.User, data: s.TeamCreate) -> s.Team:
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
    async def get_team(
        self,
        teams_service: TeamService,
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
    async def update_team(
        self,
        data: s.TeamUpdate,
        teams_service: TeamService,
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
    async def delete_team(
        self,
        teams_service: TeamService,
        team_id: Annotated[UUID, Parameter(title="Team ID", description="The team to delete.")],
    ) -> None:
        """Delete a team.

        Args:
            teams_service: Team Service
            team_id: Team ID
        """
        await teams_service.delete(team_id)
