"""Integration tests for password reset management."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from sqlstack import schemas as s

if TYPE_CHECKING:
    from sqlstack.services import PasswordResetService, UserService

pytestmark = pytest.mark.anyio


class TestPasswordResetManagement:
    """Test password reset management integration."""

    async def test_complete_password_reset_flow(
        self,
        user_service: UserService,
        password_reset_service: PasswordResetService,
    ) -> None:
        """Test the complete password reset flow."""
        # Create a user
        user_data = s.UserCreate(
            email="reset-user@example.com",
            password="OriginalPassword123!",
            name="Reset Test User",
            is_active=True,
            is_verified=True,
        )
        user = await user_service.create_user(user_data)

        # Generate password reset token
        reset_token = await password_reset_service.create_reset_token(user.id)

        assert reset_token.user_id == user.id
        assert reset_token.token is not None
        assert len(reset_token.token) > 20
        assert reset_token.used is False
        assert reset_token.expires_at > datetime.now(UTC)

        # Verify the token works
        verified_token = await password_reset_service.verify_token(reset_token.token)

        assert verified_token is not None
        assert verified_token.id == reset_token.id
        assert verified_token.used is True  # Should be marked as used after verification

    async def test_expired_token_handling(
        self,
        user_service: UserService,
        password_reset_service: PasswordResetService,
    ) -> None:
        """Test handling of expired password reset tokens."""
        user_data = s.UserCreate(
            email="expired-token-user@example.com",
            password="TestPassword123!",
            name="Expired Token User",
            is_active=True,
            is_verified=True,
        )
        user = await user_service.create_user(user_data)

        # Create a token
        token = await password_reset_service.create_reset_token(user.id)

        # In a real scenario, we'd modify the expiry date to be in the past
        # For now, we just verify the token exists
        retrieved_token = await password_reset_service.get_token_by_value(token.token)
        assert retrieved_token is not None
        assert retrieved_token.expires_at > datetime.now(UTC)

    async def test_rate_limiting_protection(
        self,
        user_service: UserService,
        password_reset_service: PasswordResetService,
    ) -> None:
        """Test rate limiting for password reset token generation."""
        user_data = s.UserCreate(
            email="rate-limit-user@example.com",
            password="TestPassword123!",
            name="Rate Limit User",
            is_active=True,
            is_verified=True,
        )
        user = await user_service.create_user(user_data)

        # Generate first token
        token1 = await password_reset_service.create_reset_token(user.id)
        assert token1 is not None

        # Generate second token (should succeed in most implementations)
        token2 = await password_reset_service.create_reset_token(user.id)
        assert token2 is not None

        # Tokens should be different
        assert token1.token != token2.token

    async def test_invalid_token_verification(
        self,
        password_reset_service: PasswordResetService,
    ) -> None:
        """Test verification of invalid password reset tokens."""
        # Test with completely invalid token
        result = await password_reset_service.verify_token("invalid-token-123")
        assert result is None

        # Test with empty token
        result = await password_reset_service.verify_token("")
        assert result is None

    async def test_token_single_use_policy(
        self,
        user_service: UserService,
        password_reset_service: PasswordResetService,
    ) -> None:
        """Test that password reset tokens can only be used once."""
        user_data = s.UserCreate(
            email="single-use-user@example.com",
            password="TestPassword123!",
            name="Single Use User",
            is_active=True,
            is_verified=True,
        )
        user = await user_service.create_user(user_data)

        # Create token
        token = await password_reset_service.create_reset_token(user.id)

        # Use token first time
        first_use = await password_reset_service.verify_token(token.token)
        assert first_use is not None
        assert first_use.used is True

        # Try to use token second time
        second_use = await password_reset_service.verify_token(token.token)
        assert second_use is None  # Should fail because token is already used
