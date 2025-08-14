"""Unit tests for UserRoleService."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from sqlstack import schemas as s

if TYPE_CHECKING:
    from sqlstack.services import UserRoleService

pytestmark = pytest.mark.anyio


class TestUserRoleService:
    """Test UserRoleService functionality."""

    async def test_assign_role_to_user(
        self,
        user_role_service: UserRoleService,
        test_user: s.User,
        test_role: s.Role,
    ) -> None:
        """Test assigning a role to a user."""
        user_role_data = s.UserRoleCreate(
            user_id=test_user.id,
            role_id=test_role.id,
        )

        user_role = await user_role_service.create(user_role_data)

        assert user_role.user_id == test_user.id
        assert user_role.role_id == test_role.id
        assert user_role.id is not None

    async def test_get_user_roles(
        self,
        user_role_service: UserRoleService,
        test_user: s.User,
        test_role: s.Role,
        user_role: s.Role,  # Default "User" role
    ) -> None:
        """Test getting all roles for a user."""
        # Assign additional role
        user_role_data = s.UserRoleCreate(
            user_id=test_user.id,
            role_id=test_role.id,
        )
        await user_role_service.create(user_role_data)

        # Also assign default user role
        default_role_data = s.UserRoleCreate(
            user_id=test_user.id,
            role_id=user_role.id,
        )
        await user_role_service.create(default_role_data)

        # Get user roles
        roles_result = await user_role_service.get_user_roles(test_user.id)

        assert roles_result.total >= 2
        role_ids = [role.role_id for role in roles_result.items]
        assert test_role.id in role_ids
        assert user_role.id in role_ids

    async def test_get_users_with_role(
        self,
        user_role_service: UserRoleService,
        test_user: s.User,
        admin_user: s.User,
        test_role: s.Role,
    ) -> None:
        """Test getting all users with a specific role."""
        # Assign role to both users
        user_role_data1 = s.UserRoleCreate(
            user_id=test_user.id,
            role_id=test_role.id,
        )
        user_role_data2 = s.UserRoleCreate(
            user_id=admin_user.id,
            role_id=test_role.id,
        )

        await user_role_service.create(user_role_data1)
        await user_role_service.create(user_role_data2)

        # Get users with the role
        users_result = await user_role_service.get_role_users(test_role.id)

        assert users_result.total >= 2
        user_ids = [user_role.user_id for user_role in users_result.items]
        assert test_user.id in user_ids
        assert admin_user.id in user_ids

    async def test_remove_role_from_user(
        self,
        user_role_service: UserRoleService,
        test_user: s.User,
        test_role: s.Role,
    ) -> None:
        """Test removing a role from a user."""
        # First assign the role
        user_role_data = s.UserRoleCreate(
            user_id=test_user.id,
            role_id=test_role.id,
        )
        user_role = await user_role_service.create(user_role_data)

        # Remove the role
        await user_role_service.delete(user_role.id)

        # Verify role is removed
        remaining_roles = await user_role_service.get_user_roles(test_user.id)
        role_ids = [role.role_id for role in remaining_roles.items]
        assert test_role.id not in role_ids

    async def test_check_user_has_role(
        self,
        user_role_service: UserRoleService,
        test_user: s.User,
        test_role: s.Role,
    ) -> None:
        """Test checking if a user has a specific role."""
        # Initially should not have the role
        has_role = await user_role_service.user_has_role(test_user.id, test_role.id)
        assert has_role is False

        # Assign the role
        user_role_data = s.UserRoleCreate(
            user_id=test_user.id,
            role_id=test_role.id,
        )
        await user_role_service.create(user_role_data)

        # Now should have the role
        has_role = await user_role_service.user_has_role(test_user.id, test_role.id)
        assert has_role is True

    async def test_check_user_has_nonexistent_role(
        self,
        user_role_service: UserRoleService,
        test_user: s.User,
    ) -> None:
        """Test checking if user has a non-existent role returns False."""
        fake_role_id = uuid4()
        has_role = await user_role_service.user_has_role(test_user.id, fake_role_id)
        assert has_role is False

    async def test_bulk_assign_roles(
        self,
        user_role_service: UserRoleService,
        test_user: s.User,
        test_role: s.Role,
        user_role: s.Role,
    ) -> None:
        """Test bulk assigning multiple roles to a user."""
        role_ids = [test_role.id, user_role.id]

        assigned_roles = await user_role_service.bulk_assign_roles(test_user.id, role_ids)

        assert len(assigned_roles) == 2
        assigned_role_ids = [role.role_id for role in assigned_roles]
        assert test_role.id in assigned_role_ids
        assert user_role.id in assigned_role_ids

        # Verify they're actually assigned
        user_roles = await user_role_service.get_user_roles(test_user.id)
        user_role_ids = [role.role_id for role in user_roles.items]
        assert test_role.id in user_role_ids
        assert user_role.id in user_role_ids

    async def test_bulk_remove_roles(
        self,
        user_role_service: UserRoleService,
        test_user: s.User,
        test_role: s.Role,
        user_role: s.Role,
    ) -> None:
        """Test bulk removing multiple roles from a user."""
        # First assign the roles
        user_role_data1 = s.UserRoleCreate(user_id=test_user.id, role_id=test_role.id)
        user_role_data2 = s.UserRoleCreate(user_id=test_user.id, role_id=user_role.id)

        await user_role_service.create(user_role_data1)
        await user_role_service.create(user_role_data2)

        # Remove roles in bulk
        role_ids = [test_role.id, user_role.id]
        await user_role_service.bulk_remove_roles(test_user.id, role_ids)

        # Verify roles are removed
        remaining_roles = await user_role_service.get_user_roles(test_user.id)
        remaining_role_ids = [role.role_id for role in remaining_roles.items]
        assert test_role.id not in remaining_role_ids
        assert user_role.id not in remaining_role_ids

    async def test_replace_user_roles(
        self,
        user_role_service: UserRoleService,
        test_user: s.User,
        test_role: s.Role,
        user_role: s.Role,
    ) -> None:
        """Test replacing all user roles with a new set."""
        # First assign some initial roles
        initial_role_data = s.UserRoleCreate(user_id=test_user.id, role_id=user_role.id)
        await user_role_service.create(initial_role_data)

        # Replace with different role
        new_roles = await user_role_service.replace_user_roles(test_user.id, [test_role.id])

        assert len(new_roles) == 1
        assert new_roles[0].role_id == test_role.id

        # Verify old role is gone and new role is present
        current_roles = await user_role_service.get_user_roles(test_user.id)
        role_ids = [role.role_id for role in current_roles.items]
        assert test_role.id in role_ids
        assert user_role.id not in role_ids

    async def test_get_role_permissions(
        self,
        user_role_service: UserRoleService,
        test_user: s.User,
        test_role: s.Role,
    ) -> None:
        """Test getting effective permissions for a user based on their roles."""
        # Assign role to user
        user_role_data = s.UserRoleCreate(user_id=test_user.id, role_id=test_role.id)
        await user_role_service.create(user_role_data)

        # Get user permissions (this would depend on how permissions are implemented)
        permissions = await user_role_service.get_user_permissions(test_user.id)

        # Basic test - permissions should be returned (exact content depends on implementation)
        assert isinstance(permissions, list)
        # In a real implementation, you'd test specific permissions based on the role
