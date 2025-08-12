"""User Account Controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Controller, delete, get, post
from litestar.di import Provide
from litestar.exceptions import HTTPException

from sqlstack import schemas as s
from sqlstack.server import deps

if TYPE_CHECKING:
    from uuid import UUID

    from sqlstack.services import TeamInvitationService
    from sqlstack.services._base import OffsetPagination


class TeamInvitationController(Controller):
    """Team Invitations."""

    tags = ["Teams"]
    dependencies = {
        "team_invitations_service": Provide(deps.provide_team_invitation_service, sync_to_thread=False),
    }

    @post(operation_id="CreateTeamInvitation", path="/{team_id:uuid}")
    async def create_team_invitation(
        self, team_invitations_service: TeamInvitationService, data: s.TeamInvitationCreate
    ) -> s.TeamInvitation:
        """Create a team invitation.

        Args:
            data: The data to create the team invitation with.
            team_invitations_service: The team invitation service.

        Returns:
            The created team invitation.
        """
        return await team_invitations_service.create(data)

    @get(operation_id="ListTeamInvitations", path="/{team_id:uuid}")
    async def list_team_invitations(
        self, team_invitations_service: TeamInvitationService, team_id: UUID
    ) -> OffsetPagination[s.TeamInvitation]:
        """List team invitations.

        Args:
            team_id: The ID of the team to list the invitations for.
            team_invitations_service: The team invitation service.

        Returns:
            The list of team invitations.
        """
        return await team_invitations_service.list_with_count(team_id=team_id)

    @delete(operation_id="DeleteTeamInvitation", path="/{team_id:uuid}/{invitation_id:uuid}")
    async def delete_team_invitation(
        self,
        team_invitations_service: TeamInvitationService,
        team_id: UUID,
        invitation_id: UUID,
    ) -> None:
        """Delete a team invitation.

        Args:
            team_id: The ID of the team to delete the invitation for.
            invitation_id: The ID of the invitation to delete.
            team_invitations_service: The team invitation service.
        """
        await team_invitations_service.delete(invitation_id)

    @post(operation_id="AcceptTeamInvitation", path="/{team_id:uuid}/{invitation_id:uuid}")
    async def accept_team_invitation(
        self,
        current_user: s.User,
        team_invitations_service: TeamInvitationService,
        team_id: UUID,
        invitation_id: UUID,
    ) -> s.Message:
        """Accept a team invitation.

        Args:
            team_id: The ID of the team to accept the invitation for.
            invitation_id: The ID of the invitation to accept.
            team_invitations_service: The team invitation service.
            current_user: The current user.

        Raises:
            HTTPException: If the user is not authorized to accept the invitation.

        Returns:
            A message indicating that the team invitation has been accepted.
        """
        invitation = await team_invitations_service.get_one(invitation_id)
        if invitation.email != current_user.email:
            raise HTTPException(status_code=400, detail="You are not authorized to accept this invitation")
        await team_invitations_service.update(invitation_id, s.TeamInvitationUpdate(accepted=True))
        return s.Message(message="Team invitation accepted")
