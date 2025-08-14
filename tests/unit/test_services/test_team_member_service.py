"""Unit tests for TeamMemberService."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from sqlstack import schemas as s

if TYPE_CHECKING:
    from sqlstack.services import TeamMemberService

pytestmark = pytest.mark.anyio


class TestTeamMemberService:
    """Test TeamMemberService functionality."""

    async def test_add_member_to_team(
        self,
        team_member_service: TeamMemberService,
        test_team: s.Team,
        test_user: s.User,
    ) -> None:
        """Test adding a member to a team."""
        member_data = s.TeamMemberCreate(
            team_id=test_team.id,
            user_id=test_user.id,
            role="MEMBER",
            is_owner=False,
        )

        member = await team_member_service.create(member_data)

        assert member.team_id == test_team.id
        assert member.user_id == test_user.id
        assert member.role == "MEMBER"
        assert member.is_owner is False
        assert member.id is not None

    async def test_add_admin_member(
        self,
        team_member_service: TeamMemberService,
        test_team: s.Team,
        admin_user: s.User,
    ) -> None:
        """Test adding an admin member to a team."""
        member_data = s.TeamMemberCreate(
            team_id=test_team.id,
            user_id=admin_user.id,
            role="ADMIN",
            is_owner=False,
        )

        member = await team_member_service.create(member_data)

        assert member.team_id == test_team.id
        assert member.user_id == admin_user.id
        assert member.role == "ADMIN"
        assert member.is_owner is False

    async def test_list_team_members(
        self,
        team_member_service: TeamMemberService,
        test_team: s.Team,
        test_user: s.User,
        admin_user: s.User,
    ) -> None:
        """Test listing members of a team."""
        # Add multiple members
        member1_data = s.TeamMemberCreate(
            team_id=test_team.id,
            user_id=test_user.id,
            role="MEMBER",
            is_owner=False,
        )
        member2_data = s.TeamMemberCreate(
            team_id=test_team.id,
            user_id=admin_user.id,
            role="ADMIN",
            is_owner=False,
        )

        await team_member_service.create(member1_data)
        await team_member_service.create(member2_data)

        # List members
        members_result = await team_member_service.list_team_members(test_team.id)

        assert members_result.total >= 2
        member_user_ids = [member.user_id for member in members_result.items]
        assert test_user.id in member_user_ids
        assert admin_user.id in member_user_ids

    async def test_get_member_by_team_and_user(
        self,
        team_member_service: TeamMemberService,
        test_team: s.Team,
        test_user: s.User,
    ) -> None:
        """Test getting a specific team member by team and user ID."""
        member_data = s.TeamMemberCreate(
            team_id=test_team.id,
            user_id=test_user.id,
            role="MEMBER",
            is_owner=False,
        )

        created_member = await team_member_service.create(member_data)
        retrieved_member = await team_member_service.get_member(test_team.id, test_user.id)

        assert retrieved_member is not None
        assert retrieved_member.id == created_member.id
        assert retrieved_member.team_id == test_team.id
        assert retrieved_member.user_id == test_user.id

    async def test_get_nonexistent_member(
        self,
        team_member_service: TeamMemberService,
        test_team: s.Team,
    ) -> None:
        """Test getting a non-existent team member returns None."""
        non_existent_user_id = uuid4()
        member = await team_member_service.get_member(test_team.id, non_existent_user_id)
        assert member is None

    async def test_update_member_role(
        self,
        team_member_service: TeamMemberService,
        test_team: s.Team,
        test_user: s.User,
    ) -> None:
        """Test updating a team member's role."""
        member_data = s.TeamMemberCreate(
            team_id=test_team.id,
            user_id=test_user.id,
            role="MEMBER",
            is_owner=False,
        )

        created_member = await team_member_service.create(member_data)

        # Update to admin
        update_data = s.TeamMemberUpdate(role="ADMIN")
        updated_member = await team_member_service.update(created_member.id, update_data)

        assert updated_member.role == "ADMIN"
        assert updated_member.id == created_member.id

    async def test_remove_team_member(
        self,
        team_member_service: TeamMemberService,
        test_team: s.Team,
        test_user: s.User,
    ) -> None:
        """Test removing a team member."""
        member_data = s.TeamMemberCreate(
            team_id=test_team.id,
            user_id=test_user.id,
            role="MEMBER",
            is_owner=False,
        )

        created_member = await team_member_service.create(member_data)

        # Remove the member
        await team_member_service.delete(created_member.id)

        # Verify member is removed
        retrieved_member = await team_member_service.get_member(test_team.id, test_user.id)
        assert retrieved_member is None

    async def test_list_user_teams(
        self,
        team_member_service: TeamMemberService,
        test_team: s.Team,
        test_user: s.User,
    ) -> None:
        """Test listing teams for a specific user."""
        member_data = s.TeamMemberCreate(
            team_id=test_team.id,
            user_id=test_user.id,
            role="MEMBER",
            is_owner=False,
        )

        await team_member_service.create(member_data)

        # List user's teams
        user_teams_result = await team_member_service.list_user_teams(test_user.id)

        assert user_teams_result.total >= 1
        team_ids = [team.id for team in user_teams_result.items]
        assert test_team.id in team_ids

    async def test_check_user_team_membership(
        self,
        team_member_service: TeamMemberService,
        test_team: s.Team,
        test_user: s.User,
    ) -> None:
        """Test checking if a user is a member of a team."""
        # Initially not a member
        is_member = await team_member_service.is_member(test_team.id, test_user.id)
        assert is_member is False

        # Add as member
        member_data = s.TeamMemberCreate(
            team_id=test_team.id,
            user_id=test_user.id,
            role="MEMBER",
            is_owner=False,
        )

        await team_member_service.create(member_data)

        # Now should be a member
        is_member = await team_member_service.is_member(test_team.id, test_user.id)
        assert is_member is True
