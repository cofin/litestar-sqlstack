"""Unit tests for UserService."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from sqlstack import schemas as s

if TYPE_CHECKING:
    from sqlstack.services import UserService

pytestmark = pytest.mark.anyio


class TestUserService:
    """Test UserService functionality."""

    async def test_create_user(self, user_service: UserService) -> None:
        """Test creating a user."""
        user_data = s.UserCreate(
            email="new@example.com",
            password="NewPassword123!",
            name="New User",
            is_active=True,
            is_verified=False,
        )

        user = await user_service.create(user_data)

        assert user.email == "new@example.com"
        assert user.name == "New User"
        assert user.is_active is True
        assert user.is_verified is False
        assert user.is_superuser is False
        assert user.id is not None

    async def test_get_user_by_id(self, user_service: UserService, test_user: s.User) -> None:
        """Test getting user by ID."""
        retrieved_user = await user_service.get_one(test_user.id)

        assert retrieved_user.id == test_user.id
        assert retrieved_user.email == test_user.email
        assert retrieved_user.name == test_user.name

    async def test_get_user_by_email(self, user_service: UserService, test_user: s.User) -> None:
        """Test getting user by email."""
        retrieved_user = await user_service.get_by_email(test_user.email)

        assert retrieved_user is not None
        assert retrieved_user.id == test_user.id
        assert retrieved_user.email == test_user.email

    async def test_get_nonexistent_user_by_email(self, user_service: UserService) -> None:
        """Test getting nonexistent user by email returns None."""
        retrieved_user = await user_service.get_by_email("nonexistent@example.com")
        assert retrieved_user is None

    async def test_update_user(self, user_service: UserService, test_user: s.User) -> None:
        """Test updating a user."""
        update_data = s.UserUpdate(name="Updated Name")

        updated_user = await user_service.update(test_user.id, update_data)

        assert updated_user.id == test_user.id
        assert updated_user.name == "Updated Name"
        assert updated_user.email == test_user.email  # Should remain unchanged

    async def test_delete_user(self, user_service: UserService, test_user: s.User) -> None:
        """Test deleting a user."""
        deleted_user = await user_service.delete(test_user.id)

        assert deleted_user.id == test_user.id

        # Verify user is actually deleted
        with pytest.raises(ValueError, match="Record not found"):
            await user_service.get_one(test_user.id)

    async def test_list_users(self, user_service: UserService, test_user: s.User, admin_user: s.User) -> None:
        """Test listing users."""
        users_page = await user_service.list()

        assert users_page.total >= 2
        assert len(users_page.items) >= 2

        user_emails = {user.email for user in users_page.items}
        assert test_user.email in user_emails
        assert admin_user.email in user_emails

    async def test_user_exists_by_email(self, user_service: UserService, test_user: s.User) -> None:
        """Test checking if user exists by email."""
        exists = await user_service.exists_by_email(test_user.email)
        assert exists is True

        not_exists = await user_service.exists_by_email("nonexistent@example.com")
        assert not_exists is False

    async def test_authenticate_valid_user(self, user_service: UserService) -> None:
        """Test authenticating with valid credentials."""
        # Create user with known password
        user_data = s.UserCreate(
            email="auth@example.com",
            password="AuthPassword123!",
            name="Auth User",
            is_active=True,
            is_verified=True,
        )
        created_user = await user_service.create(user_data)

        # Test authentication
        authenticated_user = await user_service.authenticate("auth@example.com", "AuthPassword123!")

        assert authenticated_user is not None
        assert authenticated_user.id == created_user.id
        assert authenticated_user.email == "auth@example.com"

    async def test_authenticate_invalid_password(self, user_service: UserService, test_user: s.User) -> None:
        """Test authentication with invalid password."""
        with pytest.raises(ValueError, match="Invalid credentials"):
            await user_service.authenticate(test_user.email, "WrongPassword123!")

    async def test_authenticate_nonexistent_user(self, user_service: UserService) -> None:
        """Test authentication with nonexistent user."""
        with pytest.raises(ValueError, match="Invalid credentials"):
            await user_service.authenticate("nonexistent@example.com", "SomePassword123!")

    async def test_authenticate_inactive_user(self, user_service: UserService) -> None:
        """Test authentication with inactive user."""
        # Create inactive user
        user_data = s.UserCreate(
            email="inactive@example.com",
            password="InactivePassword123!",
            name="Inactive User",
            is_active=False,
            is_verified=True,
        )
        await user_service.create(user_data)

        with pytest.raises(ValueError, match="User account is inactive"):
            await user_service.authenticate("inactive@example.com", "InactivePassword123!")

    async def test_get_user_by_id_not_found(self, user_service: UserService) -> None:
        """Test getting user by non-existent ID raises error."""
        non_existent_id = uuid4()

        with pytest.raises(ValueError, match="Record not found"):
            await user_service.get_one(non_existent_id)
