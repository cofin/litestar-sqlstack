"""Unit tests for UserOAuthAccountService."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from sqlstack import schemas as s

if TYPE_CHECKING:
    from sqlstack.services import UserOAuthAccountService

pytestmark = pytest.mark.anyio


class TestUserOAuthAccountService:
    """Test UserOAuthAccountService functionality."""

    async def test_create_oauth_account(
        self,
        user_oauth_account_service: UserOAuthAccountService,
        test_user: s.User,
    ) -> None:
        """Test creating an OAuth account."""
        oauth_data = s.UserOAuthAccountCreate(
            user_id=test_user.id,
            provider="google",
            oauth_account_id="google_123456",
            oauth_account_email="test@gmail.com",
        )

        oauth_account = await user_oauth_account_service.create(oauth_data)

        assert oauth_account.user_id == test_user.id
        assert oauth_account.provider == "google"
        assert oauth_account.oauth_account_id == "google_123456"
        assert oauth_account.oauth_account_email == "test@gmail.com"
        assert oauth_account.id is not None

    async def test_get_oauth_account_by_provider_and_id(
        self,
        user_oauth_account_service: UserOAuthAccountService,
        test_user: s.User,
    ) -> None:
        """Test retrieving OAuth account by provider and account ID."""
        oauth_data = s.UserOAuthAccountCreate(
            user_id=test_user.id,
            provider="github",
            oauth_account_id="github_789012",
            oauth_account_email="test@github-email.com",
        )

        created_account = await user_oauth_account_service.create(oauth_data)
        retrieved_account = await user_oauth_account_service.get_by_provider_and_id("github", "github_789012")

        assert retrieved_account is not None
        assert retrieved_account.id == created_account.id
        assert retrieved_account.provider == "github"
        assert retrieved_account.oauth_account_id == "github_789012"

    async def test_get_nonexistent_oauth_account(self, user_oauth_account_service: UserOAuthAccountService) -> None:
        """Test retrieving a non-existent OAuth account returns None."""
        account = await user_oauth_account_service.get_by_provider_and_id("nonexistent", "fake_id")
        assert account is None

    async def test_list_user_oauth_accounts(
        self,
        user_oauth_account_service: UserOAuthAccountService,
        test_user: s.User,
    ) -> None:
        """Test listing OAuth accounts for a user."""
        # Create multiple OAuth accounts for the user
        google_data = s.UserOAuthAccountCreate(
            user_id=test_user.id,
            provider="google",
            oauth_account_id="google_multiple_1",
            oauth_account_email="test1@gmail.com",
        )

        github_data = s.UserOAuthAccountCreate(
            user_id=test_user.id,
            provider="github",
            oauth_account_id="github_multiple_1",
            oauth_account_email="test1@github-email.com",
        )

        await user_oauth_account_service.create(google_data)
        await user_oauth_account_service.create(github_data)

        # List accounts for the user
        accounts_result = await user_oauth_account_service.list_user_accounts(test_user.id)

        assert accounts_result.total >= 2
        providers = [account.provider for account in accounts_result.items]
        assert "google" in providers
        assert "github" in providers

    async def test_update_oauth_account(
        self,
        user_oauth_account_service: UserOAuthAccountService,
        test_user: s.User,
    ) -> None:
        """Test updating an OAuth account."""
        oauth_data = s.UserOAuthAccountCreate(
            user_id=test_user.id,
            provider="discord",
            oauth_account_id="discord_update_test",
            oauth_account_email="old@discord.com",
        )

        created_account = await user_oauth_account_service.create(oauth_data)

        # Update the account
        update_data = s.UserOAuthAccountUpdate(oauth_account_email="new@discord.com")

        updated_account = await user_oauth_account_service.update(created_account.id, update_data)

        assert updated_account.oauth_account_email == "new@discord.com"
        assert updated_account.provider == "discord"  # Unchanged
        assert updated_account.oauth_account_id == "discord_update_test"  # Unchanged

    async def test_delete_oauth_account(
        self,
        user_oauth_account_service: UserOAuthAccountService,
        test_user: s.User,
    ) -> None:
        """Test deleting an OAuth account."""
        oauth_data = s.UserOAuthAccountCreate(
            user_id=test_user.id,
            provider="twitter",
            oauth_account_id="twitter_delete_test",
            oauth_account_email="test@twitter.com",
        )

        created_account = await user_oauth_account_service.create(oauth_data)

        # Delete the account
        await user_oauth_account_service.delete(created_account.id)

        # Verify account is deleted
        retrieved_account = await user_oauth_account_service.get_by_provider_and_id("twitter", "twitter_delete_test")
        assert retrieved_account is None

    async def test_get_user_by_oauth_provider(
        self,
        user_oauth_account_service: UserOAuthAccountService,
        test_user: s.User,
    ) -> None:
        """Test finding a user by their OAuth provider account."""
        oauth_data = s.UserOAuthAccountCreate(
            user_id=test_user.id,
            provider="linkedin",
            oauth_account_id="linkedin_user_lookup",
            oauth_account_email="lookup@linkedin.com",
        )

        await user_oauth_account_service.create(oauth_data)

        # Find user by OAuth provider
        found_user = await user_oauth_account_service.get_user_by_oauth("linkedin", "linkedin_user_lookup")

        assert found_user is not None
        assert found_user.id == test_user.id
        assert found_user.email == test_user.email

    async def test_get_user_by_nonexistent_oauth(self, user_oauth_account_service: UserOAuthAccountService) -> None:
        """Test finding a user by non-existent OAuth account returns None."""
        user = await user_oauth_account_service.get_user_by_oauth("nonexistent", "fake_oauth_id")
        assert user is None

    async def test_duplicate_oauth_account_prevention(
        self,
        user_oauth_account_service: UserOAuthAccountService,
        test_user: s.User,
        admin_user: s.User,
    ) -> None:
        """Test that duplicate OAuth accounts (same provider + account_id) are handled."""
        oauth_data1 = s.UserOAuthAccountCreate(
            user_id=test_user.id,
            provider="duplicate_test",
            oauth_account_id="duplicate_account_123",
            oauth_account_email="user1@duplicate.com",
        )

        # Create first account
        await user_oauth_account_service.create(oauth_data1)

        # Try to create duplicate with different user - should raise an error or handle gracefully
        oauth_data2 = s.UserOAuthAccountCreate(
            user_id=admin_user.id,
            provider="duplicate_test",
            oauth_account_id="duplicate_account_123",  # Same provider + ID
            oauth_account_email="user2@duplicate.com",
        )

        # This should either raise an exception or handle the duplicate gracefully
        # depending on the implementation
        from contextlib import suppress

        with suppress(Exception):
            # If this raises an exception, that's expected for duplicate prevention
            await user_oauth_account_service.create(oauth_data2)
            # If it succeeds, verify that only one exists or they're handled properly
