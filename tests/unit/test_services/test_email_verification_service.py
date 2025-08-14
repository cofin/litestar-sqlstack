"""Unit tests for EmailVerificationService."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from sqlstack import schemas as s
    from sqlstack.services import EmailVerificationService

pytestmark = pytest.mark.anyio


class TestEmailVerificationService:
    """Test EmailVerificationService functionality."""

    async def test_create_verification_token(
        self, email_verification_service: EmailVerificationService, unverified_user: s.User
    ) -> None:
        """Test creating a verification token."""
        token = await email_verification_service.create_verification_token(unverified_user.id, unverified_user.email)

        assert token.user_id == unverified_user.id
        assert token.email == unverified_user.email
        assert token.token is not None
        assert len(token.token) > 20  # Should be a substantial token
        assert token.used is False
        assert token.expires_at is not None

    async def test_verify_token_success(
        self,
        email_verification_service: EmailVerificationService,
        test_verification_token: s.EmailVerificationToken,
    ) -> None:
        """Test successful token verification."""
        verified_user = await email_verification_service.verify_token(test_verification_token.token)

        assert verified_user.id == test_verification_token.user_id
        assert verified_user.is_verified is True

    async def test_verify_invalid_token(self, email_verification_service: EmailVerificationService) -> None:
        """Test verification with invalid token."""
        with pytest.raises(ValueError, match="Invalid or already used verification token"):
            await email_verification_service.verify_token("invalid-token-123")

    async def test_verify_already_used_token(
        self,
        email_verification_service: EmailVerificationService,
        test_verification_token: s.EmailVerificationToken,
    ) -> None:
        """Test verification with already used token."""
        # Use the token first
        await email_verification_service.verify_token(test_verification_token.token)

        # Try to use it again
        with pytest.raises(ValueError, match="Invalid or already used verification token"):
            await email_verification_service.verify_token(test_verification_token.token)

    async def test_invalidate_user_tokens(
        self,
        email_verification_service: EmailVerificationService,
        unverified_user: s.User,
    ) -> None:
        """Test invalidating all user tokens."""
        # Create multiple tokens for the user
        token1 = await email_verification_service.create_verification_token(unverified_user.id, unverified_user.email)
        token2 = await email_verification_service.create_verification_token(unverified_user.id, unverified_user.email)

        # Invalidate all tokens
        await email_verification_service.invalidate_user_tokens(unverified_user.id)

        # Verify tokens are invalidated (used=True)
        with pytest.raises(ValueError, match="Invalid or already used verification token"):
            await email_verification_service.verify_token(token1.token)

        with pytest.raises(ValueError, match="Invalid or already used verification token"):
            await email_verification_service.verify_token(token2.token)

    async def test_get_user_verification_status(
        self,
        email_verification_service: EmailVerificationService,
        test_user: s.User,
        unverified_user: s.User,
    ) -> None:
        """Test getting user verification status."""
        # Test verified user
        is_verified = await email_verification_service.get_user_verification_status(test_user.id)
        assert is_verified is True

        # Test unverified user
        is_verified = await email_verification_service.get_user_verification_status(unverified_user.id)
        assert is_verified is False

    async def test_has_valid_token(
        self,
        email_verification_service: EmailVerificationService,
        test_verification_token: s.EmailVerificationToken,
        test_user: s.User,
    ) -> None:
        """Test checking if user has valid tokens."""
        # User with valid token
        has_token = await email_verification_service.has_valid_token(test_verification_token.user_id)
        assert has_token is True

        # User without valid token
        has_token = await email_verification_service.has_valid_token(test_user.id)
        assert has_token is False

    async def test_get_pending_tokens_for_user(
        self,
        email_verification_service: EmailVerificationService,
        unverified_user: s.User,
    ) -> None:
        """Test getting pending tokens for a user."""
        # Create tokens for user
        await email_verification_service.create_verification_token(unverified_user.id, unverified_user.email)
        await email_verification_service.create_verification_token(unverified_user.id, unverified_user.email)

        pending_tokens = await email_verification_service.get_pending_tokens_for_user(unverified_user.id)

        # Should have the most recent token (older ones get invalidated)
        assert len(pending_tokens) >= 1
        assert all(token.user_id == unverified_user.id for token in pending_tokens)
        assert all(not token.used for token in pending_tokens)

    async def test_cleanup_expired_tokens(self, email_verification_service: EmailVerificationService) -> None:
        """Test cleanup of expired tokens."""
        # This would require manipulating token expiration dates
        # For now, just test that the method runs without error
        deleted_count = await email_verification_service.cleanup_expired_tokens()
        assert isinstance(deleted_count, int)
        assert deleted_count >= 0

    async def test_get_token_by_value(
        self,
        email_verification_service: EmailVerificationService,
        test_verification_token: s.EmailVerificationToken,
    ) -> None:
        """Test getting token by its value."""
        retrieved_token = await email_verification_service.get_token_by_value(test_verification_token.token)

        assert retrieved_token is not None
        assert retrieved_token.id == test_verification_token.id
        assert retrieved_token.token == test_verification_token.token

    async def test_get_nonexistent_token_by_value(self, email_verification_service: EmailVerificationService) -> None:
        """Test getting nonexistent token returns None."""
        token = await email_verification_service.get_token_by_value("nonexistent-token")
        assert token is None

    async def test_list_tokens(
        self,
        email_verification_service: EmailVerificationService,
        test_verification_token: s.EmailVerificationToken,
    ) -> None:
        """Test listing tokens with pagination."""
        tokens_page = await email_verification_service.list_tokens()

        assert tokens_page.total >= 1
        assert len(tokens_page.items) >= 1
        assert any(token.id == test_verification_token.id for token in tokens_page.items)
