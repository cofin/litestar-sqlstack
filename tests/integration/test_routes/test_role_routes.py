"""Test RoleController HTTP endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    from litestar.testing import AsyncTestClient

    from sqlstack import schemas as s


@pytest.mark.anyio
class TestRoleRoutes:
    """Test Role HTTP endpoints."""

    @pytest.mark.parametrize("authenticated_headers", ["superuser"], indirect=True)
    async def test_list_roles(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
    ) -> None:
        """Test listing roles."""
        response = await client.get("/api/roles", headers=authenticated_headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        # Should include default roles
        assert data["total"] >= 2

    @pytest.mark.parametrize("authenticated_headers", ["superuser"], indirect=True)
    async def test_create_role(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
    ) -> None:
        """Test creating a role."""
        role_data = {"name": "Test API Role", "slug": "test-api-role", "description": "Role created via API test"}

        response = await client.post("/api/roles", json=role_data, headers=authenticated_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == role_data["name"]
        assert data["slug"] == role_data["slug"]
        assert data["description"] == role_data["description"]
        assert "id" in data
        assert "createdAt" in data

    @pytest.mark.parametrize("authenticated_headers", ["superuser"], indirect=True)
    async def test_get_role(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
        test_role: s.Role,
    ) -> None:
        """Test retrieving a specific role."""
        response = await client.get(f"/api/roles/{test_role.id}", headers=authenticated_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_role.id)
        assert data["name"] == test_role.name
        assert data["slug"] == test_role.slug

    @pytest.mark.parametrize("authenticated_headers", ["superuser"], indirect=True)
    async def test_update_role(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
        test_role: s.Role,
    ) -> None:
        """Test updating a role."""
        update_data = {"name": "Updated API Role", "description": "Updated via API test"}

        response = await client.patch(f"/api/roles/{test_role.id}", json=update_data, headers=authenticated_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert data["slug"] == test_role.slug  # Slug unchanged

    @pytest.mark.parametrize("authenticated_headers", ["superuser"], indirect=True)
    async def test_update_default_role_denied(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
        user_role: s.Role,
    ) -> None:
        """Test that updating default roles is denied."""
        update_data = {
            "name": "User",  # Default role name
            "description": "Attempted update",
        }

        response = await client.patch(f"/api/roles/{user_role.id}", json=update_data, headers=authenticated_headers)

        assert response.status_code == 400
        assert "Cannot update default roles" in response.json()["detail"]

    @pytest.mark.parametrize("authenticated_headers", ["superuser"], indirect=True)
    async def test_delete_role(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
        test_role: s.Role,
    ) -> None:
        """Test deleting a role."""
        response = await client.delete(f"/api/roles/{test_role.id}", headers=authenticated_headers)

        assert response.status_code == 204

        # Verify role is deleted
        get_response = await client.get(f"/api/roles/{test_role.id}", headers=authenticated_headers)
        assert get_response.status_code == 404

    @pytest.mark.parametrize("authenticated_headers", ["superuser"], indirect=True)
    async def test_delete_default_role_denied(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
        user_role: s.Role,
    ) -> None:
        """Test that deleting default roles is denied."""
        response = await client.delete(f"/api/roles/{user_role.id}", headers=authenticated_headers)

        assert response.status_code == 400
        assert "Cannot delete default roles" in response.json()["detail"]

    async def test_get_role_not_found(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
    ) -> None:
        """Test retrieving a non-existent role."""
        non_existent_id = uuid4()
        response = await client.get(f"/api/roles/{non_existent_id}", headers=authenticated_headers)

        assert response.status_code == 404

    @pytest.mark.parametrize("authenticated_headers", ["user"], indirect=True)
    async def test_user_access_denied(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
    ) -> None:
        """Test that regular users cannot access role endpoints."""
        # List roles
        response = await client.get("/api/roles", headers=authenticated_headers)
        assert response.status_code == 403

        # Create role
        role_data = {"name": "Unauthorized Role", "slug": "unauthorized-role"}
        response = await client.post("/api/roles", json=role_data, headers=authenticated_headers)
        assert response.status_code == 403

    async def test_unauthenticated_access_denied(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that unauthenticated requests are denied."""
        response = await client.get("/api/roles")
        assert response.status_code == 401

        response = await client.post("/api/roles", json={"name": "test"})
        assert response.status_code == 401
