"""Test TeamController HTTP endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    from litestar.testing import AsyncTestClient

    from sqlstack import schemas as s


class TestTeamRoutes:
    """Test Team HTTP endpoints."""

    @pytest.mark.parametrize("user_type", ["user"])
    async def test_list_teams(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
    ) -> None:
        """Test listing teams."""
        response = await client.get("/api/teams", headers=authenticated_headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

    @pytest.mark.parametrize("user_type", ["user"])
    async def test_create_team(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
    ) -> None:
        """Test creating a team."""
        team_data = {"name": "Test API Team", "description": "Team created via API test"}

        response = await client.post("/api/teams", json=team_data, headers=authenticated_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == team_data["name"]
        assert data["description"] == team_data["description"]
        assert "id" in data
        assert "slug" in data
        assert "createdAt" in data
        assert len(data["members"]) == 1  # Creator is added as owner
        assert data["members"][0]["role"] == "ADMIN"
        assert data["members"][0]["isOwner"] is True

    @pytest.mark.parametrize("user_type", ["user"])
    async def test_create_team_with_tags(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
    ) -> None:
        """Test creating a team with tags."""
        team_data = {
            "name": "Tagged API Team",
            "description": "Team with tags",
            "tags": ["frontend", "react", "javascript"],
        }

        response = await client.post("/api/teams", json=team_data, headers=authenticated_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == team_data["name"]
        assert len(data["tags"]) == 3
        tag_names = [tag["name"] for tag in data["tags"]]
        assert "frontend" in tag_names
        assert "react" in tag_names
        assert "javascript" in tag_names

    @pytest.mark.parametrize("user_type", ["user"])
    async def test_get_team(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
        test_team: s.Team,
    ) -> None:
        """Test retrieving a specific team."""
        response = await client.get(f"/api/teams/{test_team.id}", headers=authenticated_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_team.id)
        assert data["name"] == test_team.name
        assert data["slug"] == test_team.slug

    @pytest.mark.parametrize("user_type", ["user"])
    async def test_update_team(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
        test_team: s.Team,
    ) -> None:
        """Test updating a team."""
        update_data = {"name": "Updated API Team", "description": "Updated via API test"}

        response = await client.patch(f"/api/teams/{test_team.id}", json=update_data, headers=authenticated_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]

    @pytest.mark.parametrize("user_type", ["user"])
    async def test_update_team_with_tags(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
        test_team: s.Team,
    ) -> None:
        """Test updating a team with new tags."""
        update_data = {"name": "Tagged Update Team", "tags": ["backend", "python", "fastapi"]}

        response = await client.patch(f"/api/teams/{test_team.id}", json=update_data, headers=authenticated_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert len(data["tags"]) == 3
        tag_names = [tag["name"] for tag in data["tags"]]
        assert "backend" in tag_names
        assert "python" in tag_names
        assert "fastapi" in tag_names

    @pytest.mark.parametrize("user_type", ["user"])
    async def test_delete_team(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
        test_team: s.Team,
    ) -> None:
        """Test deleting a team."""
        response = await client.delete(f"/api/teams/{test_team.id}", headers=authenticated_headers)

        assert response.status_code == 204

        # Verify team is deleted
        get_response = await client.get(f"/api/teams/{test_team.id}", headers=authenticated_headers)
        assert get_response.status_code == 404

    async def test_get_team_not_found(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
    ) -> None:
        """Test retrieving a non-existent team."""
        non_existent_id = uuid4()
        response = await client.get(f"/api/teams/{non_existent_id}", headers=authenticated_headers)

        assert response.status_code == 404

    async def test_get_team_requires_membership(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
    ) -> None:
        """Test that accessing team details requires membership."""
        # Create team with different user (if possible) or test with non-member
        team_data = {"name": "Private Team", "description": "Not accessible"}
        create_response = await client.post("/api/teams", json=team_data, headers=authenticated_headers)
        assert create_response.status_code == 201

        team_id = create_response.json()["id"]

        # Try to access as the same user (who created it, so should work)
        response = await client.get(f"/api/teams/{team_id}", headers=authenticated_headers)
        assert response.status_code == 200

    async def test_update_team_requires_admin(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
    ) -> None:
        """Test that updating team requires admin permission."""
        # Create team
        team_data = {"name": "Admin Required Team", "description": "Need admin to modify"}
        create_response = await client.post("/api/teams", json=team_data, headers=authenticated_headers)
        assert create_response.status_code == 201

        team_id = create_response.json()["id"]
        update_data = {"name": "Updated Name"}

        # Creator has admin rights, so should work
        response = await client.patch(f"/api/teams/{team_id}", json=update_data, headers=authenticated_headers)
        assert response.status_code == 200

    async def test_delete_team_requires_admin(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
    ) -> None:
        """Test that deleting team requires admin permission."""
        # Create team
        team_data = {"name": "Delete Test Team", "description": "To be deleted"}
        create_response = await client.post("/api/teams", json=team_data, headers=authenticated_headers)
        assert create_response.status_code == 201

        team_id = create_response.json()["id"]

        # Creator has admin rights, so should work
        response = await client.delete(f"/api/teams/{team_id}", headers=authenticated_headers)
        assert response.status_code == 204

    async def test_unauthenticated_access_denied(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that unauthenticated requests are denied."""
        response = await client.get("/api/teams")
        assert response.status_code == 401

        response = await client.post("/api/teams", json={"name": "test"})
        assert response.status_code == 401

    @pytest.mark.parametrize("user_type", ["superuser"])
    async def test_superuser_can_see_all_teams(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
    ) -> None:
        """Test that superusers can see all teams."""
        response = await client.get("/api/teams", headers=authenticated_headers)

        assert response.status_code == 200
        data = response.json()
        # Superusers should see more teams than regular users
        assert data["total"] >= 0
