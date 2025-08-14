"""Unit tests for PasswordResetService."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    from sqlstack.services import PasswordResetService

pytestmark = pytest.mark.anyio


class TestPasswordResetService:
    """Test PasswordResetService functionality."""

    async def test_create_reset_token(self, password_reset_service: PasswordResetService) -> None:
        """Test creating a password reset token."""
        user_id = uuid4()

        token = await password_reset_service.create_reset_token(user_id)

        assert token.user_id == user_id
        assert token.token is not None
        assert len(token.token) > 20  # Should be a secure token
        assert token.expires_at > datetime.now(UTC)
        assert token.used is False
        assert token.id is not None

    async def test_get_token_by_value(self, password_reset_service: PasswordResetService) -> None:
        """Test retrieving a token by its value."""
        user_id = uuid4()
        created_token = await password_reset_service.create_reset_token(user_id)

        retrieved_token = await password_reset_service.get_token_by_value(created_token.token)

        assert retrieved_token is not None
        assert retrieved_token.id == created_token.id
        assert retrieved_token.token == created_token.token
        assert retrieved_token.user_id == user_id

    async def test_get_nonexistent_token_by_value(self, password_reset_service: PasswordResetService) -> None:
        """Test retrieving a non-existent token returns None."""
        token = await password_reset_service.get_token_by_value("non-existent-token")
        assert token is None

    async def test_verify_token_success(self, password_reset_service: PasswordResetService) -> None:
        """Test successfully verifying a valid token."""
        user_id = uuid4()
        created_token = await password_reset_service.create_reset_token(user_id)

        verified_token = await password_reset_service.verify_token(created_token.token)

        assert verified_token is not None
        assert verified_token.id == created_token.id
        assert verified_token.used is True  # Should be marked as used

    async def test_verify_invalid_token(self, password_reset_service: PasswordResetService) -> None:
        """Test verifying an invalid token returns None."""
        verified_token = await password_reset_service.verify_token("invalid-token")
        assert verified_token is None

    async def test_verify_already_used_token(self, password_reset_service: PasswordResetService) -> None:
        """Test verifying an already used token returns None."""
        user_id = uuid4()
        created_token = await password_reset_service.create_reset_token(user_id)

        # Use the token once
        first_verification = await password_reset_service.verify_token(created_token.token)
        assert first_verification is not None

        # Try to use it again
        second_verification = await password_reset_service.verify_token(created_token.token)
        assert second_verification is None

    async def test_cleanup_expired_tokens(self, password_reset_service: PasswordResetService) -> None:
        """Test cleaning up expired tokens."""
        # This test depends on the implementation having a cleanup method
        # For now, we'll create tokens and test basic functionality
        user_id = uuid4()
        token = await password_reset_service.create_reset_token(user_id)

        # Verify the token exists
        retrieved = await password_reset_service.get_token_by_value(token.token)
        assert retrieved is not None

        # In a real implementation, we'd test cleanup with expired tokens
        # This is a placeholder for that functionality

    async def test_multiple_tokens_per_user(self, password_reset_service: PasswordResetService) -> None:
        """Test that multiple tokens can be created for the same user."""
        user_id = uuid4()

        token1 = await password_reset_service.create_reset_token(user_id)
        token2 = await password_reset_service.create_reset_token(user_id)

        assert token1.id != token2.id
        assert token1.token != token2.token
        assert token1.user_id == token2.user_id == user_id

        # Both tokens should be valid
        retrieved1 = await password_reset_service.get_token_by_value(token1.token)
        retrieved2 = await password_reset_service.get_token_by_value(token2.token)

        assert retrieved1 is not None
        assert retrieved2 is not None
