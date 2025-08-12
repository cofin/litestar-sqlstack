"""User Account Controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from litestar import Controller, delete, post
from litestar.di import Provide
from litestar.exceptions import HTTPException
from litestar.params import Parameter
from litestar.status_codes import HTTP_202_ACCEPTED

from sqlstack.server import deps

if TYPE_CHECKING:
    from uuid import UUID

    from sqlstack import schemas as s
    from sqlstack.services import TeamMemberService, TeamService, UserService


class TeamMemberController(Controller):
    """Team Members."""

    tags = ["Team Members"]
    dependencies = {
        "teams_service": Provide(deps.provide_team_service, sync_to_thread=False),
        "team_members_service": Provide(deps.provide_team_member_service, sync_to_thread=False),
        "users_service": Provide(deps.provide_users_service, sync_to_thread=False),
    }

    @post(operation_id="AddMemberToTeam", path="/api/teams/{team_id:uuid}/members")
    async def add_member_to_team(
        self,
        teams_service: TeamService,
        users_service: UserService,
        data: s.TeamMemberModify,
        team_id: Annotated[UUID, Parameter(title="Team ID", description="The team to update.")],
    ) -> s.Team:
        """Add a member to a team.

        Args:
            teams_service: Team Service
            users_service: User Service
            data: Team Member Modify
            team_id: Team ID

        Raises:
            IntegrityError: If the user is already a member of the team.

        Returns:
            Team
        """
        # Validate team exists
        await teams_service.get_one(team_id)
        user = await users_service.get_by_email(data.user_name)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        # Add member to team using team service
        await teams_service.add_member(team_id, user.id, "MEMBER")
        return await teams_service.get_one(team_id)

    @delete(
        operation_id="RemoveMemberFromTeam", path="/api/teams/{team_id:uuid}/members", status_code=HTTP_202_ACCEPTED
    )
    async def remove_member_from_team(
        self,
        teams_service: TeamService,
        team_members_service: TeamMemberService,
        users_service: UserService,
        data: s.TeamMemberModify,
        team_id: Annotated[UUID, Parameter(title="Team ID", description="The team to delete.")],
    ) -> s.Team:
        """Revoke a members access to a team.

        Args:
            teams_service: Team Service
            team_members_service: Team Member Service
            users_service: User Service
            data: Team Member Modify
            team_id: Team ID

        Raises:
            IntegrityError: If the user is not a member of the team.

        Returns:
            Team
        """
        user = await users_service.get_by_email(data.user_name)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        # Remove member from team using team service
        await teams_service.remove_member(team_id, user.id)
        return await teams_service.get_one(team_id)
