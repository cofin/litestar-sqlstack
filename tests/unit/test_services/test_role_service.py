"""Test RoleService functionality."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from sqlstack import schemas as s

if TYPE_CHECKING:
    from sqlstack.services import RoleService


class TestRoleService:
    """Test RoleService CRUD operations."""

    async def test_create_role(self, role_service: RoleService) -> None:
        """Test creating a new role."""
        role_data = s.RoleCreate(name="Test Role")

        created_role = await role_service.create(role_data)

        assert created_role.name == "Test Role"
        assert created_role.slug is not None  # Should be auto-generated
        assert created_role.id is not None
        assert created_role.created_at is not None

    async def test_get_role_by_id(self, role_service: RoleService, test_role: s.Role) -> None:
        """Test retrieving a role by ID."""
        retrieved_role = await role_service.get_one(test_role.id)

        assert retrieved_role.id == test_role.id
        assert retrieved_role.name == test_role.name
        assert retrieved_role.slug == test_role.slug

    async def test_get_role_not_found(self, role_service: RoleService) -> None:
        """Test retrieving a non-existent role raises error."""
        non_existent_id = uuid4()

        with pytest.raises(ValueError):
            await role_service.get_one(non_existent_id)

    async def test_update_role(self, role_service: RoleService, test_role: s.Role) -> None:
        """Test updating a role."""
        update_data = s.RoleUpdate(name="Updated Role Name")

        updated_role = await role_service.update(test_role.id, update_data)

        assert updated_role.id == test_role.id
        assert updated_role.name == "Updated Role Name"
        assert updated_role.slug == test_role.slug  # Slug unchanged

    async def test_delete_role(self, role_service: RoleService, test_role: s.Role) -> None:
        """Test deleting a role."""
        deleted_role = await role_service.delete(test_role.id)

        assert deleted_role.id == test_role.id

        # Verify role is deleted
        with pytest.raises(ValueError):
            await role_service.get_one(test_role.id)

    async def test_list_roles(self, role_service: RoleService) -> None:
        """Test listing roles with pagination."""
        # Create multiple roles
        for i in range(5):
            role_data = s.RoleCreate(name=f"Role {i}")
            await role_service.create(role_data)

        result = await role_service.list_with_count()

        # Should include default roles plus created ones
        assert result.total >= 5
        assert len(result.items) >= 5
        assert result.limit == 20  # Default limit
        assert result.offset == 0

    async def test_get_by_slug(self, role_service: RoleService, test_role: s.Role) -> None:
        """Test retrieving a role by slug."""
        retrieved_role = await role_service.get_by_slug(test_role.slug)

        assert retrieved_role is not None
        assert retrieved_role.id == test_role.id
        assert retrieved_role.slug == test_role.slug

    async def test_get_by_slug_not_found(self, role_service: RoleService) -> None:
        """Test retrieving a non-existent role by slug."""
        retrieved_role = await role_service.get_by_slug("non-existent-slug")

        assert retrieved_role is None

    async def test_get_default_role(self, role_service: RoleService) -> None:
        """Test retrieving the default user role."""
        default_role = await role_service.get_default_role()

        assert default_role is not None
        assert default_role.name == "User"

    async def test_create_default_roles(self, role_service: RoleService) -> None:
        """Test ensuring default roles exist."""
        # This method creates default roles if they don't exist
        await role_service.ensure_default_roles()

        # Verify default roles exist
        user_role = await role_service.get_by_name("User")
        superuser_role = await role_service.get_by_name("Superuser")

        assert user_role is not None
        assert user_role.name == "User"
        assert superuser_role is not None
        assert superuser_role.name == "Superuser"

    async def test_get_by_name(self, role_service: RoleService, test_role: s.Role) -> None:
        """Test retrieving a role by name."""
        retrieved_role = await role_service.get_by_name(test_role.name)

        assert retrieved_role is not None
        assert retrieved_role.id == test_role.id
        assert retrieved_role.name == test_role.name

    async def test_get_by_name_not_found(self, role_service: RoleService) -> None:
        """Test retrieving a non-existent role by name."""
        retrieved_role = await role_service.get_by_name("Non-existent Role")

        assert retrieved_role is None
