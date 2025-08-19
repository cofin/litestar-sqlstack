"""Unit tests for TeamInvitationService."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from sqlstack import schemas as s

if TYPE_CHECKING:
    from sqlstack.services import TeamInvitationService

pytestmark = pytest.mark.anyio


class TestTeamInvitationService:
    """Test TeamInvitationService functionality."""

    async def test_create_invitation(
        self,
        team_invitation_service: TeamInvitationService,
        test_team: s.Team,
        test_user: s.User,
    ) -> None:
        """Test creating a team invitation."""
        invitation_data = s.TeamInvitationCreate(
            team_id=test_team.id,
            invited_by_user_id=test_user.id,
            invited_email="newmember@example.com",
            role="MEMBER",
        )

        invitation = await team_invitation_service.create(invitation_data)

        assert invitation.team_id == test_team.id
        assert invitation.invited_by_user_id == test_user.id
        assert invitation.invited_email == "newmember@example.com"
        assert invitation.role == "MEMBER"
        assert invitation.status == "PENDING"
        assert invitation.token is not None
        assert len(invitation.token) > 20  # Should be a secure token
        assert invitation.expires_at > datetime.now(UTC)
        assert invitation.id is not None

    async def test_get_invitation_by_token(
        self,
        team_invitation_service: TeamInvitationService,
        test_team: s.Team,
        test_user: s.User,
    ) -> None:
        """Test retrieving an invitation by its token."""
        invitation_data = s.TeamInvitationCreate(
            team_id=test_team.id,
            invited_by_user_id=test_user.id,
            invited_email="token-test@example.com",
            role="ADMIN",
        )

        created_invitation = await team_invitation_service.create(invitation_data)
        retrieved_invitation = await team_invitation_service.get_by_token(created_invitation.token)

        assert retrieved_invitation is not None
        assert retrieved_invitation.id == created_invitation.id
        assert retrieved_invitation.token == created_invitation.token
        assert retrieved_invitation.invited_email == "token-test@example.com"

    async def test_get_nonexistent_invitation_by_token(self, team_invitation_service: TeamInvitationService) -> None:
        """Test retrieving a non-existent invitation by token returns None."""
        invitation = await team_invitation_service.get_by_token("non-existent-token")
        assert invitation is None

    async def test_list_team_invitations(
        self,
        team_invitation_service: TeamInvitationService,
        test_team: s.Team,
        test_user: s.User,
    ) -> None:
        """Test listing invitations for a team."""
        invitation1_data = s.TeamInvitationCreate(
            team_id=test_team.id,
            invited_by_user_id=test_user.id,
            invited_email="invite1@example.com",
            role="MEMBER",
        )

        invitation2_data = s.TeamInvitationCreate(
            team_id=test_team.id,
            invited_by_user_id=test_user.id,
            invited_email="invite2@example.com",
            role="ADMIN",
        )

        await team_invitation_service.create(invitation1_data)
        await team_invitation_service.create(invitation2_data)

        invitations_result = await team_invitation_service.list_team_invitations(test_team.id)

        assert invitations_result.total >= 2
        invitation_emails = [inv.invited_email for inv in invitations_result.items]
        assert "invite1@example.com" in invitation_emails
        assert "invite2@example.com" in invitation_emails

    async def test_accept_invitation(
        self,
        team_invitation_service: TeamInvitationService,
        test_team: s.Team,
        test_user: s.User,
    ) -> None:
        """Test accepting an invitation."""
        invitation_data = s.TeamInvitationCreate(
            team_id=test_team.id,
            invited_by_user_id=test_user.id,
            invited_email="accept-test@example.com",
            role="MEMBER",
        )

        created_invitation = await team_invitation_service.create(invitation_data)
        accepted_user_id = uuid4()

        accepted_invitation = await team_invitation_service.accept_invitation(
            created_invitation.token, accepted_user_id
        )

        assert accepted_invitation is not None
        assert accepted_invitation.status == "ACCEPTED"
        assert accepted_invitation.accepted_by_user_id == accepted_user_id
        assert accepted_invitation.accepted_at is not None

    async def test_accept_nonexistent_invitation(self, team_invitation_service: TeamInvitationService) -> None:
        """Test accepting a non-existent invitation returns None."""
        result = await team_invitation_service.accept_invitation("invalid-token", uuid4())
        assert result is None

    async def test_decline_invitation(
        self,
        team_invitation_service: TeamInvitationService,
        test_team: s.Team,
        test_user: s.User,
    ) -> None:
        """Test declining an invitation."""
        invitation_data = s.TeamInvitationCreate(
            team_id=test_team.id,
            invited_by_user_id=test_user.id,
            invited_email="decline-test@example.com",
            role="MEMBER",
        )

        created_invitation = await team_invitation_service.create(invitation_data)

        declined_invitation = await team_invitation_service.decline_invitation(created_invitation.token)

        assert declined_invitation is not None
        assert declined_invitation.status == "DECLINED"
        assert declined_invitation.declined_at is not None

    async def test_cancel_invitation(
        self,
        team_invitation_service: TeamInvitationService,
        test_team: s.Team,
        test_user: s.User,
    ) -> None:
        """Test canceling an invitation."""
        invitation_data = s.TeamInvitationCreate(
            team_id=test_team.id,
            invited_by_user_id=test_user.id,
            invited_email="cancel-test@example.com",
            role="MEMBER",
        )

        created_invitation = await team_invitation_service.create(invitation_data)

        # Cancel the invitation
        await team_invitation_service.delete(created_invitation.id)

        # Verify invitation is deleted
        retrieved_invitation = await team_invitation_service.get_by_token(created_invitation.token)
        assert retrieved_invitation is None

    async def test_list_pending_invitations_by_email(
        self,
        team_invitation_service: TeamInvitationService,
        test_team: s.Team,
        test_user: s.User,
    ) -> None:
        """Test listing pending invitations for a specific email."""
        email = "pending-test@example.com"

        invitation_data = s.TeamInvitationCreate(
            team_id=test_team.id,
            invited_by_user_id=test_user.id,
            invited_email=email,
            role="MEMBER",
        )

        await team_invitation_service.create(invitation_data)

        pending_invitations = await team_invitation_service.list_pending_invitations(email)

        assert pending_invitations.total >= 1
        invitation_emails = [inv.invited_email for inv in pending_invitations.items]
        assert email in invitation_emails

        # All should be pending
        for invitation in pending_invitations.items:
            assert invitation.status == "PENDING"

    async def test_cleanup_expired_invitations(
        self,
        team_invitation_service: TeamInvitationService,
        test_team: s.Team,
        test_user: s.User,
    ) -> None:
        """Test cleaning up expired invitations."""
        invitation_data = s.TeamInvitationCreate(
            team_id=test_team.id,
            invited_by_user_id=test_user.id,
            invited_email="cleanup-test@example.com",
            role="MEMBER",
        )

        invitation = await team_invitation_service.create(invitation_data)

        # Verify invitation exists
        retrieved = await team_invitation_service.get_by_token(invitation.token)
        assert retrieved is not None

        # In a real implementation, we'd manipulate the expiry date and test cleanup
        # This is a placeholder for that functionality
