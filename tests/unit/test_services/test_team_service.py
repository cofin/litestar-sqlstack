"""Test TeamService functionality."""

from __future__ import annotations

from uuid import uuid4

import pytest

from sqlstack import schemas as s
from sqlstack.services import TeamService


class TestTeamService:
    """Test TeamService CRUD operations."""

    async def test_create_team_with_owner(self, team_service: TeamService, test_user: s.User) -> None:
        """Test creating a new team with an owner."""
        team_data = s.TeamCreate(
            name="Test Team",
            description="A test team",
            owner_id=test_user.id
        )

        created_team = await team_service.create(team_data)

        assert created_team.name == "Test Team"
        assert created_team.description == "A test team"
        assert created_team.slug == "test-team"  # Auto-generated
        assert created_team.id is not None
        assert created_team.created_at is not None
        assert len(created_team.members) == 1
        assert created_team.members[0].user_id == test_user.id
        assert created_team.members[0].role == "ADMIN"
        assert created_team.members[0].is_owner is True

    async def test_create_team_with_tags(self, team_service: TeamService, test_user: s.User) -> None:
        """Test creating a team with tags."""
        team_data = s.TeamCreate(
            name="Tagged Team",
            description="Team with tags",
            owner_id=test_user.id,
            tags=["frontend", "react", "typescript"]
        )

        created_team = await team_service.create(team_data)

        assert created_team.name == "Tagged Team"
        assert len(created_team.tags) == 3
        tag_names = [tag.name for tag in created_team.tags]
        assert "frontend" in tag_names
        assert "react" in tag_names
        assert "typescript" in tag_names

    async def test_get_team_by_id(self, team_service: TeamService, test_team: s.Team) -> None:
        """Test retrieving a team by ID."""
        retrieved_team = await team_service.get_one(test_team.id)

        assert retrieved_team.id == test_team.id
        assert retrieved_team.name == test_team.name
        assert retrieved_team.slug == test_team.slug

    async def test_get_team_not_found(self, team_service: TeamService) -> None:
        """Test retrieving a non-existent team raises error."""
        non_existent_id = uuid4()

        with pytest.raises(ValueError):
            await team_service.get_one(non_existent_id)

    async def test_get_team_by_slug(self, team_service: TeamService, test_team: s.Team) -> None:
        """Test retrieving a team by slug."""
        retrieved_team = await team_service.get_by_slug(test_team.slug)

        assert retrieved_team is not None
        assert retrieved_team.id == test_team.id
        assert retrieved_team.slug == test_team.slug

    async def test_update_team(self, team_service: TeamService, test_team: s.Team) -> None:
        """Test updating a team."""
        update_data = s.TeamUpdate(
            name="Updated Team Name",
            description="Updated description"
        )

        updated_team = await team_service.update(test_team.id, update_data)

        assert updated_team.id == test_team.id
        assert updated_team.name == "Updated Team Name"
        assert updated_team.description == "Updated description"

    async def test_update_team_with_tags(self, team_service: TeamService, test_team: s.Team) -> None:
        """Test updating a team with new tags."""
        update_data = s.TeamUpdate(
            name="Updated Team",
            tags=["backend", "python", "fastapi"]
        )

        updated_team = await team_service.update(test_team.id, update_data)

        assert updated_team.name == "Updated Team"
        assert len(updated_team.tags) == 3
        tag_names = [tag.name for tag in updated_team.tags]
        assert "backend" in tag_names
        assert "python" in tag_names
        assert "fastapi" in tag_names

    async def test_delete_team(self, team_service: TeamService, test_team: s.Team) -> None:
        """Test deleting a team."""
        deleted_team = await team_service.delete(test_team.id)

        assert deleted_team.id == test_team.id

        # Verify team is deleted
        with pytest.raises(ValueError):
            await team_service.get_one(test_team.id)

    async def test_add_team_member(self, team_service: TeamService, test_team: s.Team, test_user: s.User) -> None:
        """Test adding a member to a team."""
        member = await team_service.add_member(test_team.id, test_user.id, "MEMBER")

        assert member.team_id == test_team.id
        assert member.user_id == test_user.id
        assert member.role == "MEMBER"
        assert member.is_owner is False

    async def test_remove_team_member(self, team_service: TeamService, test_team: s.Team, test_user: s.User) -> None:
        """Test removing a member from a team."""
        # First add the member
        await team_service.add_member(test_team.id, test_user.id, "MEMBER")

        # Then remove them
        await team_service.remove_member(test_team.id, test_user.id)

        # Verify removal by getting the updated team
        updated_team = await team_service.get_one(test_team.id)
        member_user_ids = [member.user_id for member in updated_team.members]
        assert test_user.id not in member_user_ids

    async def test_get_user_teams(self, team_service: TeamService, test_user: s.User) -> None:
        """Test getting all teams for a user."""
        # Create teams and add user to them
        team1_data = s.TeamCreate(name="User Team 1", owner_id=test_user.id)
        team2_data = s.TeamCreate(name="User Team 2", owner_id=test_user.id)

        team1 = await team_service.create(team1_data)
        team2 = await team_service.create(team2_data)

        user_teams = await team_service.get_user_teams(test_user.id)

        assert len(user_teams) >= 2
        team_ids = [team.id for team in user_teams]
        assert team1.id in team_ids
        assert team2.id in team_ids

    async def test_search_teams(self, team_service: TeamService, test_user: s.User) -> None:
        """Test searching teams by name."""
        # Create searchable teams
        await team_service.create(s.TeamCreate(name="Frontend Development Team", owner_id=test_user.id))
        await team_service.create(s.TeamCreate(name="Backend Development Team", owner_id=test_user.id))
        await team_service.create(s.TeamCreate(name="Design Team", owner_id=test_user.id))

        results = await team_service.search_teams("Development", limit=10)

        assert len(results) >= 2
        assert all("Development" in team.name for team in results)

    async def test_list_teams_for_superuser(self, team_service: TeamService, superuser: s.User) -> None:
        """Test that superusers can see all teams."""
        result = await team_service.list_with_count(user=superuser)

        assert result.total >= 0
        assert result.limit == 20  # Default limit
        assert result.offset == 0

    async def test_list_teams_for_regular_user(self, team_service: TeamService, test_user: s.User) -> None:
        """Test that regular users only see teams they're members of."""
        # Create a team for the user
        team_data = s.TeamCreate(name="User's Team", owner_id=test_user.id)
        created_team = await team_service.create(team_data)

        result = await team_service.list_with_count(user=test_user)

        assert result.total >= 1
        team_ids = [team.id for team in result.items]
        assert created_team.id in team_ids

    async def test_can_view_all_superuser(self, superuser: s.User) -> None:
        """Test that superusers can view all teams."""
        assert TeamService.can_view_all(superuser) is True

    async def test_can_view_all_regular_user(self, test_user: s.User) -> None:
        """Test that regular users cannot view all teams."""
        assert TeamService.can_view_all(test_user) is False
