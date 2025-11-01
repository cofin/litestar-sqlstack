"""Team member routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from litestar import Controller, delete, post
from litestar.params import Parameter
from litestar.status_codes import HTTP_202_ACCEPTED

from sqlstack import schemas as s
from sqlstack.lib.di import Inject, inject
from sqlstack.services import TeamMemberService, TeamService, UserService


class TeamMemberController(Controller):
    """Team Members."""

    tags = ["Team Members"]
    signature_types = [TeamService, TeamMemberService, UserService, s, UUID]

    @post(operation_id="AddMemberToTeam", path="/api/teams/{team_id:uuid}/members")
    @inject
    async def add_member_to_team(
        self,
        teams_service: Inject[TeamService],
        team_members_service: Inject[TeamMemberService],
        users_service: Inject[UserService],
        data: s.TeamMemberCreate,
        team_id: Annotated[UUID, Parameter(title="Team ID", description="The team to update.")],
    ) -> s.TeamMember:
        """Add a member to a team.

        Args:
            teams_service: Team Service
            users_service: User Service
            data: Team Member Create
            team_id: Team ID

        Returns:
            TeamMember
        """
        await teams_service.get_team(team_id)

        # Validate user exists
        await users_service.get_user(data.user_id)

        role_value = s.TeamRoles(data.role.upper()) if isinstance(data.role, str) else s.TeamRoles.MEMBER
        return await team_members_service.add_member_to_team(team_id, data.user_id, role_value)

    @delete(
        operation_id="RemoveMemberFromTeam",
        path="/api/teams/{team_id:uuid}/members/{user_id:uuid}",
        status_code=HTTP_202_ACCEPTED,
    )
    @inject
    async def remove_member_from_team(
        self,
        teams_service: Inject[TeamService],
        team_members_service: Inject[TeamMemberService],
        team_id: Annotated[UUID, Parameter(title="Team ID", description="The team to update.")],
        user_id: Annotated[UUID, Parameter(title="User ID", description="The user to remove from the team.")],
    ) -> None:
        """Revoke a member's access to a team.

        Args:
            teams_service: Team Service
            team_id: Team ID
            user_id: User ID
        """
        await teams_service.get_team(team_id)

        await team_members_service.remove_member_from_team(team_id, user_id)
