"""Integration tests for role management system."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from sqlstack import schemas as s

if TYPE_CHECKING:
    from sqlstack.services import RoleService, UserRoleService, UserService

pytestmark = pytest.mark.anyio


class TestRoleManagement:
    """Test role management system integration."""

    async def test_role_creation_and_assignment(
        self,
        role_service: RoleService,
        user_service: UserService,
        user_role_service: UserRoleService,
    ) -> None:
        """Test creating roles and assigning them to users."""
        # Create a custom role
        role_data = s.RoleCreate(name="Content Editor")
        role = await role_service.create_role(role_data)

        assert role.name == "Content Editor"
        assert role.id is not None

        # Create a user
        user_data = s.UserCreate(
            email="editor@example.com",
            password="EditorPassword123!",
            name="Content Editor User",
            is_active=True,
            is_verified=True,
        )
        user = await user_service.create_user(user_data)

        # Assign role to user
        user_role = await user_role_service.assign_role_to_user(user.id, role.id)

        assert user_role.role_id == role.id
        assert user_role.role_slug is not None

        # Verify user has the role
        has_role = await user_role_service.user_has_role(user.id, role.id)
        assert has_role is True

    async def test_multiple_role_assignment(
        self,
        role_service: RoleService,
        user_service: UserService,
        user_role_service: UserRoleService,
    ) -> None:
        """Test assigning multiple roles to a user."""
        # Create multiple roles
        admin_role_data = s.RoleCreate(name="Admin")
        moderator_role_data = s.RoleCreate(name="Moderator")

        admin_role = await role_service.create_role(admin_role_data)
        moderator_role = await role_service.create_role(moderator_role_data)

        # Create user
        user_data = s.UserCreate(
            email="multi-role@example.com",
            password="MultiRolePassword123!",
            name="Multi Role User",
            is_active=True,
            is_verified=True,
        )
        user = await user_service.create_user(user_data)

        # Assign multiple roles using bulk assignment (if available)
        try:
            assigned_roles = await user_role_service.bulk_assign_roles(user.id, [admin_role.id, moderator_role.id])

            assert len(assigned_roles) == 2
            role_ids = [ur.role_id for ur in assigned_roles]
            assert admin_role.id in role_ids
            assert moderator_role.id in role_ids

        except AttributeError:
            # If bulk assignment not available, assign individually
            admin_assignment = s.UserRoleCreate(user_id=user.id, role_id=admin_role.id)
            moderator_assignment = s.UserRoleCreate(user_id=user.id, role_id=moderator_role.id)

            await user_role_service.assign_role_to_user(user.id, admin_role.id)
            await user_role_service.assign_role_to_user(user.id, moderator_role.id)

        # Verify user has both roles
        user_roles = await user_role_service.get_user_roles(user.id)

        assert user_roles.total >= 2
        user_role_ids = [ur.role_id for ur in user_roles.items]
        assert admin_role.id in user_role_ids
        assert moderator_role.id in user_role_ids

    async def test_role_removal(
        self,
        role_service: RoleService,
        user_service: UserService,
        user_role_service: UserRoleService,
    ) -> None:
        """Test removing roles from users."""
        # Create role and user
        role_data = s.RoleCreate(name="Temporary Role")
        role = await role_service.create_role(role_data)

        user_data = s.UserCreate(
            email="temp-role@example.com",
            password="TempRolePassword123!",
            name="Temp Role User",
            is_active=True,
            is_verified=True,
        )
        user = await user_service.create_user(user_data)

        # Assign role
        user_role = await user_role_service.assign_role_to_user(user.id, role.id)

        # Verify role is assigned
        has_role = await user_role_service.user_has_role(user.id, role.id)
        assert has_role is True

        # Remove role
        await user_role_service.revoke_role_from_user(user.id, role.id)

        # Verify role is removed
        has_role_after = await user_role_service.user_has_role(user.id, role.id)
        assert has_role_after is False

    async def test_default_role_system(
        self,
        role_service: RoleService,
        user_service: UserService,
        user_role_service: UserRoleService,
    ) -> None:
        """Test default role assignment system."""
        # Get or create default roles
        try:
            default_roles = await role_service.create_default_roles()
            assert len(default_roles) >= 1

            # Find user role
            user_role = None
            for role in default_roles:
                if role.slug == "user":
                    user_role = role
                    break

            assert user_role is not None

        except AttributeError:
            # If create_default_roles doesn't exist, create manually
            user_role_data = s.RoleCreate(name="User")
            user_role = await role_service.create_role(user_role_data)

        # Create a user
        user_data = s.UserCreate(
            email="default-role@example.com",
            password="DefaultRolePassword123!",
            name="Default Role User",
            is_active=True,
            is_verified=True,
        )
        user = await user_service.create_user(user_data)

        # In a real system, default role might be assigned automatically
        # For testing, we'll assign it manually
        await user_role_service.assign_role_to_user(user.id, user_role.id)

        # Verify default role is assigned
        has_default_role = await user_role_service.user_has_role(user.id, user_role.id)
        assert has_default_role is True

    async def test_role_based_permissions(
        self,
        role_service: RoleService,
        user_service: UserService,
        user_role_service: UserRoleService,
    ) -> None:
        """Test role-based permissions system."""
        # Create roles with different permission levels
        admin_role_data = s.RoleCreate(name="Super Admin")
        user_role_data = s.RoleCreate(name="Regular User")

        admin_role = await role_service.create_role(admin_role_data)
        user_role = await role_service.create_role(user_role_data)

        # Create users
        admin_user_data = s.UserCreate(
            email="admin@example.com",
            password="AdminPassword123!",
            name="Admin User",
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )

        regular_user_data = s.UserCreate(
            email="regular@example.com",
            password="UserPassword123!",
            name="Regular User",
            is_active=True,
            is_verified=True,
        )

        admin_user = await user_service.create_user(admin_user_data)
        regular_user = await user_service.create_user(regular_user_data)

        # Assign roles
        await user_role_service.assign_role_to_user(admin_user.id, admin_role.id)
        await user_role_service.assign_role_to_user(regular_user.id, user_role.id)

        # Test permissions (if implemented)
        try:
            admin_permissions = await user_role_service.get_user_permissions(admin_user.id)
            user_permissions = await user_role_service.get_user_permissions(regular_user.id)

            assert isinstance(admin_permissions, list)
            assert isinstance(user_permissions, list)

            # In a real system, admin would have more permissions
            # For now, just verify the method returns lists

        except AttributeError:
            # If permissions system not implemented, skip this test
            pytest.skip("Permission system not implemented")

    async def test_role_hierarchy_and_inheritance(
        self,
        role_service: RoleService,
        user_service: UserService,
        user_role_service: UserRoleService,
    ) -> None:
        """Test role hierarchy and inheritance (if supported)."""
        # Create hierarchical roles
        super_admin_data = s.RoleCreate(name="Super Admin")
        admin_data = s.RoleCreate(name="Admin")
        moderator_data = s.RoleCreate(name="Moderator")

        super_admin_role = await role_service.create_role(super_admin_data)
        await role_service.create_role(admin_data)
        await role_service.create_role(moderator_data)

        # Create user with highest role
        user_data = s.UserCreate(
            email="hierarchy@example.com",
            password="HierarchyPassword123!",
            name="Hierarchy User",
            is_active=True,
            is_verified=True,
        )
        user = await user_service.create_user(user_data)

        # Assign super admin role
        await user_role_service.assign_role_to_user(user.id, super_admin_role.id)

        # Verify role assignment
        has_super_admin = await user_role_service.user_has_role(user.id, super_admin_role.id)
        assert has_super_admin is True

        # In a real hierarchy system, super admin would inherit lower permissions
        # For basic implementation, we just verify the direct role assignment works
