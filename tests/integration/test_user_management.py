"""Integration tests for user management endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from litestar.testing import AsyncTestClient

    from sqlstack import schemas as s

pytestmark = pytest.mark.anyio


class TestUserManagementEndpoints:
    """Test user management endpoints."""

    async def test_list_users_as_admin(self, admin_client: AsyncTestClient, test_user: s.User) -> None:
        """Test listing users as admin."""
        response = await admin_client.get("/api/users")

        assert response.status_code == 200
        users_data = response.json()

        assert "items" in users_data
        assert "total" in users_data
        assert users_data["total"] >= 1

        # Check that our test user is in the list
        user_emails = [user["email"] for user in users_data["items"]]
        assert test_user.email in user_emails

    async def test_list_users_as_regular_user(self, authenticated_client: AsyncTestClient) -> None:
        """Test listing users as regular user (should be forbidden)."""
        response = await authenticated_client.get("/api/users")

        # Regular users shouldn't be able to list all users
        assert response.status_code in [403, 401]

    async def test_get_user_by_id_as_admin(self, admin_client: AsyncTestClient, test_user: s.User) -> None:
        """Test getting specific user by ID as admin."""
        response = await admin_client.get(f"/api/users/{test_user.id}")

        assert response.status_code == 200
        user_data = response.json()

        assert user_data["id"] == str(test_user.id)
        assert user_data["email"] == test_user.email
        assert user_data["name"] == test_user.name

    async def test_get_nonexistent_user_as_admin(self, admin_client: AsyncTestClient) -> None:
        """Test getting nonexistent user as admin."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await admin_client.get(f"/api/users/{fake_uuid}")

        assert response.status_code == 404

    async def test_create_user_as_admin(self, admin_client: AsyncTestClient) -> None:
        """Test creating user as admin."""
        user_data = {
            "email": "admin_created@example.com",
            "password": "AdminCreatedPassword123!",
            "name": "Admin Created User",
            "isActive": True,
            "isVerified": False,
        }

        response = await admin_client.post("/api/users", json=user_data)

        assert response.status_code == 200
        created_user = response.json()

        assert created_user["email"] == "admin_created@example.com"
        assert created_user["name"] == "Admin Created User"
        assert created_user["isActive"] is True
        assert created_user["isVerified"] is False
        assert "id" in created_user

    async def test_update_user_as_admin(self, admin_client: AsyncTestClient, test_user: s.User) -> None:
        """Test updating user as admin."""
        update_data = {
            "name": "Updated by Admin",
        }

        response = await admin_client.patch(f"/api/users/{test_user.id}", json=update_data)

        assert response.status_code == 200
        updated_user = response.json()

        assert updated_user["id"] == str(test_user.id)
        assert updated_user["name"] == "Updated by Admin"
        assert updated_user["email"] == test_user.email  # Should remain unchanged

    async def test_delete_user_as_admin(self, admin_client: AsyncTestClient) -> None:
        """Test deleting user as admin."""
        # First create a user to delete
        user_data = {
            "email": "todelete@example.com",
            "password": "ToDeletePassword123!",
            "name": "To Delete User",
            "isActive": True,
        }

        create_response = await admin_client.post("/api/users", json=user_data)
        assert create_response.status_code == 200
        created_user = create_response.json()
        user_id = created_user["id"]

        # Now delete the user
        delete_response = await admin_client.delete(f"/api/users/{user_id}")
        assert delete_response.status_code == 200

        # Verify user is deleted
        get_response = await admin_client.get(f"/api/users/{user_id}")
        assert get_response.status_code == 404

    async def test_create_user_as_regular_user(self, authenticated_client: AsyncTestClient) -> None:
        """Test creating user as regular user (should be forbidden)."""
        user_data = {
            "email": "forbidden@example.com",
            "password": "ForbiddenPassword123!",
            "name": "Forbidden User",
        }

        response = await authenticated_client.post("/api/users", json=user_data)

        # Regular users shouldn't be able to create users
        assert response.status_code in [403, 401]

    async def test_update_user_as_regular_user(self, authenticated_client: AsyncTestClient, admin_user: s.User) -> None:
        """Test updating another user as regular user (should be forbidden)."""
        update_data = {
            "name": "Unauthorized Update",
        }

        response = await authenticated_client.patch(f"/api/users/{admin_user.id}", json=update_data)

        # Regular users shouldn't be able to update other users
        assert response.status_code in [403, 401]

    async def test_delete_user_as_regular_user(self, authenticated_client: AsyncTestClient, admin_user: s.User) -> None:
        """Test deleting user as regular user (should be forbidden)."""
        response = await authenticated_client.delete(f"/api/users/{admin_user.id}")

        # Regular users shouldn't be able to delete users
        assert response.status_code in [403, 401]

    async def test_unauthorized_access_to_user_endpoints(self, client: AsyncTestClient) -> None:
        """Test unauthorized access to user endpoints."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"

        # Test all endpoints without authentication
        endpoints = [
            ("GET", "/api/users"),
            ("GET", f"/api/users/{fake_uuid}"),
            ("POST", "/api/users"),
            ("PATCH", f"/api/users/{fake_uuid}"),
            ("DELETE", f"/api/users/{fake_uuid}"),
        ]

        for method, endpoint in endpoints:
            if method == "GET":
                response = await client.get(endpoint)
            elif method == "POST":
                response = await client.post(endpoint, json={})
            elif method == "PATCH":
                response = await client.patch(endpoint, json={})
            elif method == "DELETE":
                response = await client.delete(endpoint)

            # Should require authentication
            assert response.status_code in [401, 403]
