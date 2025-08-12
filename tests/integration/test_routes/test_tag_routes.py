"""Test TagController HTTP endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    from litestar.testing import AsyncTestClient

    from sqlstack import schemas as s


class TestTagRoutes:
    """Test Tag HTTP endpoints."""

    @pytest.mark.parametrize("user_type", ["superuser"])
    async def test_list_tags(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
    ) -> None:
        """Test listing tags."""
        response = await client.get("/api/tags", headers=authenticated_headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

    @pytest.mark.parametrize("user_type", ["superuser"])
    async def test_create_tag(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
    ) -> None:
        """Test creating a tag."""
        tag_data = {
            "name": "Test API Tag",
            "slug": "test-api-tag",
            "description": "Tag created via API test"
        }

        response = await client.post("/api/tags", json=tag_data, headers=authenticated_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == tag_data["name"]
        assert data["slug"] == tag_data["slug"]
        assert data["description"] == tag_data["description"]
        assert "id" in data
        assert "createdAt" in data

    @pytest.mark.parametrize("user_type", ["superuser"])
    async def test_get_tag(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
        test_tag: s.Tag,
    ) -> None:
        """Test retrieving a specific tag."""
        response = await client.get(f"/api/tags/{test_tag.id}", headers=authenticated_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_tag.id)
        assert data["name"] == test_tag.name
        assert data["slug"] == test_tag.slug

    @pytest.mark.parametrize("user_type", ["superuser"])
    async def test_update_tag(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
        test_tag: s.Tag,
    ) -> None:
        """Test updating a tag."""
        update_data = {
            "name": "Updated API Tag",
            "description": "Updated via API test"
        }

        response = await client.patch(f"/api/tags/{test_tag.id}", json=update_data, headers=authenticated_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert data["slug"] == test_tag.slug  # Slug unchanged

    @pytest.mark.parametrize("user_type", ["superuser"])
    async def test_delete_tag(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
        test_tag: s.Tag,
    ) -> None:
        """Test deleting a tag."""
        response = await client.delete(f"/api/tags/{test_tag.id}", headers=authenticated_headers)

        assert response.status_code == 204

        # Verify tag is deleted
        get_response = await client.get(f"/api/tags/{test_tag.id}", headers=authenticated_headers)
        assert get_response.status_code == 404

    async def test_get_tag_not_found(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
    ) -> None:
        """Test retrieving a non-existent tag."""
        non_existent_id = uuid4()
        response = await client.get(f"/api/tags/{non_existent_id}", headers=authenticated_headers)

        assert response.status_code == 404

    @pytest.mark.parametrize("user_type", ["user"])
    async def test_create_tag_requires_superuser(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
    ) -> None:
        """Test that creating tags requires superuser permission."""
        tag_data = {
            "name": "Unauthorized Tag",
            "slug": "unauthorized-tag"
        }

        response = await client.post("/api/tags", json=tag_data, headers=authenticated_headers)

        assert response.status_code == 403

    @pytest.mark.parametrize("user_type", ["user"])
    async def test_update_tag_requires_superuser(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
        test_tag: s.Tag,
    ) -> None:
        """Test that updating tags requires superuser permission."""
        update_data = {
            "name": "Unauthorized Update"
        }

        response = await client.patch(f"/api/tags/{test_tag.id}", json=update_data, headers=authenticated_headers)

        assert response.status_code == 403

    @pytest.mark.parametrize("user_type", ["user"])
    async def test_delete_tag_requires_superuser(
        self,
        client: AsyncTestClient,
        authenticated_headers: dict[str, str],
        test_tag: s.Tag,
    ) -> None:
        """Test that deleting tags requires superuser permission."""
        response = await client.delete(f"/api/tags/{test_tag.id}", headers=authenticated_headers)

        assert response.status_code == 403

    async def test_unauthenticated_access_denied(
        self,
        client: AsyncTestClient,
    ) -> None:
        """Test that unauthenticated requests are denied."""
        response = await client.get("/api/tags")
        assert response.status_code == 401

        response = await client.post("/api/tags", json={"name": "test"})
        assert response.status_code == 401
