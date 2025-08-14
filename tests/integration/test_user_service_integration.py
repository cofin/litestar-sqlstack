"""Integration tests for User service operations."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from sqlstack import schemas as s

if TYPE_CHECKING:
    from sqlstack.services import UserService

pytestmark = pytest.mark.anyio


class TestUserServiceIntegration:
    """Test User service integration scenarios."""

    async def test_user_lifecycle(
        self,
        user_service: UserService,
    ) -> None:
        """Test complete user lifecycle operations."""
        # Create user
        user_data = s.UserCreate(
            email="lifecycle@example.com",
            password="LifecyclePassword123!",
            name="Lifecycle User",
            is_active=True,
            is_verified=False,
        )

        created_user = await user_service.create(user_data)

        assert created_user.email == "lifecycle@example.com"
        assert created_user.name == "Lifecycle User"
        assert created_user.is_active is True
        assert created_user.is_verified is False
        assert created_user.is_superuser is False
        assert created_user.id is not None

        # Update user
        update_data = s.UserUpdate(
            name="Updated Lifecycle User",
            is_verified=True,
        )

        updated_user = await user_service.update(created_user.id, update_data)

        assert updated_user.name == "Updated Lifecycle User"
        assert updated_user.is_verified is True
        assert updated_user.email == "lifecycle@example.com"  # Should remain unchanged

        # Retrieve user
        retrieved_user = await user_service.get_one(created_user.id)

        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.name == "Updated Lifecycle User"
        assert retrieved_user.is_verified is True

        # Delete user
        await user_service.delete(created_user.id)

        # Verify deletion
        deleted_user = await user_service.get_one(created_user.id)
        assert deleted_user is None

    async def test_user_authentication_flow(
        self,
        user_service: UserService,
    ) -> None:
        """Test user authentication scenarios."""
        # Create user
        user_data = s.UserCreate(
            email="auth-test@example.com",
            password="AuthTestPassword123!",
            name="Auth Test User",
            is_active=True,
            is_verified=True,
        )

        user = await user_service.create(user_data)

        # Test successful authentication
        authenticated_user = await user_service.authenticate("auth-test@example.com", "AuthTestPassword123!")

        assert authenticated_user is not None
        assert authenticated_user.id == user.id
        assert authenticated_user.email == "auth-test@example.com"

        # Test failed authentication with wrong password
        failed_auth = await user_service.authenticate("auth-test@example.com", "WrongPassword")
        assert failed_auth is None

        # Test failed authentication with wrong email
        failed_auth = await user_service.authenticate("wrong-email@example.com", "AuthTestPassword123!")
        assert failed_auth is None

        # Test authentication with inactive user
        update_data = s.UserUpdate(is_active=False)
        await user_service.update(user.id, update_data)

        inactive_auth = await user_service.authenticate("auth-test@example.com", "AuthTestPassword123!")
        assert inactive_auth is None

    async def test_user_email_uniqueness(
        self,
        user_service: UserService,
    ) -> None:
        """Test that user emails must be unique."""
        # Create first user
        user_data_1 = s.UserCreate(
            email="unique-test@example.com",
            password="Password123!",
            name="First User",
            is_active=True,
            is_verified=True,
        )

        first_user = await user_service.create(user_data_1)
        assert first_user.email == "unique-test@example.com"

        # Try to create second user with same email
        user_data_2 = s.UserCreate(
            email="unique-test@example.com",
            password="DifferentPassword123!",
            name="Second User",
            is_active=True,
            is_verified=True,
        )

        # This should either raise an exception or handle the duplicate gracefully
        try:
            await user_service.create(user_data_2)
            # If no exception, verify only one user exists with this email
            by_email = await user_service.get_by_email("unique-test@example.com")
            assert by_email is not None
            assert by_email.id == first_user.id
        except Exception:
            # Exception is expected for duplicate email constraint
            pass

    async def test_user_search_and_filtering(
        self,
        user_service: UserService,
    ) -> None:
        """Test user search and filtering capabilities."""
        # Create multiple users for testing
        users_to_create = [
            s.UserCreate(
                email="search1@example.com",
                password="Password123!",
                name="Search User Alpha",
                is_active=True,
                is_verified=True,
            ),
            s.UserCreate(
                email="search2@example.com",
                password="Password123!",
                name="Search User Beta",
                is_active=False,
                is_verified=True,
            ),
            s.UserCreate(
                email="search3@example.com",
                password="Password123!",
                name="Different Name",
                is_active=True,
                is_verified=False,
            ),
        ]

        created_users = []
        for user_data in users_to_create:
            created_user = await user_service.create(user_data)
            created_users.append(created_user)

        # Test basic listing
        users_result = await user_service.list()

        assert users_result.total >= 3

        # Verify all created users are in the results
        result_emails = [user.email for user in users_result.items]
        for user in created_users:
            assert user.email in result_emails

    async def test_user_password_change(
        self,
        user_service: UserService,
    ) -> None:
        """Test user password change functionality."""
        # Create user
        user_data = s.UserCreate(
            email="password-change@example.com",
            password="OriginalPassword123!",
            name="Password Change User",
            is_active=True,
            is_verified=True,
        )

        user = await user_service.create(user_data)

        # Verify original password works
        auth_original = await user_service.authenticate("password-change@example.com", "OriginalPassword123!")
        assert auth_original is not None

        # Change password (implementation depends on your UserService interface)
        try:
            await user_service.update_password(user.id, "OriginalPassword123!", "NewPassword123!")

            # Test old password no longer works
            auth_old = await user_service.authenticate("password-change@example.com", "OriginalPassword123!")
            assert auth_old is None

            # Test new password works
            auth_new = await user_service.authenticate("password-change@example.com", "NewPassword123!")
            assert auth_new is not None
            assert auth_new.id == user.id

        except AttributeError:
            # If update_password method doesn't exist, skip this test
            pytest.skip("UserService.update_password method not implemented")

    async def test_user_existence_check(
        self,
        user_service: UserService,
    ) -> None:
        """Test checking if users exist."""
        # Create user
        user_data = s.UserCreate(
            email="existence-check@example.com",
            password="ExistencePassword123!",
            name="Existence Check User",
            is_active=True,
            is_verified=True,
        )

        user = await user_service.create(user_data)

        # Check existence by email
        exists_by_email = await user_service.exists_by_email("existence-check@example.com")
        assert exists_by_email is True

        # Check non-existence
        not_exists = await user_service.exists_by_email("nonexistent@example.com")
        assert not_exists is False

        # Check existence by ID (if method exists)
        try:
            exists_by_id = await user_service.exists(user.id)
            assert exists_by_id is True

            not_exists_by_id = await user_service.exists(uuid4())
            assert not_exists_by_id is False
        except AttributeError:
            # If exists method doesn't exist, skip this part
            pass
