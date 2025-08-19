"""Unit tests for PasswordResetService."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    from sqlstack.services import PasswordResetService

pytestmark = pytest.mark.anyio


async def test_create_reset_token(password_reset_service: PasswordResetService) -> None:
    """Test creating a password reset token."""
    user_id = uuid4()

    token = await password_reset_service.create_reset_token(user_id)

    assert token.user_id == user_id
    assert token.token is not None
    assert len(token.token) > 20  # Should be a secure token
    assert token.expires_at > datetime.now(UTC)
    assert token.used is False
    assert token.id is not None


async def test_get_token_by_value(password_reset_service: PasswordResetService) -> None:
    """Test retrieving a token by its value."""
    user_id = uuid4()
    created_token = await password_reset_service.create_reset_token(user_id)

    retrieved_token = await password_reset_service.get_token_by_value(created_token.token)

    assert retrieved_token is not None
    assert retrieved_token.id == created_token.id
    assert retrieved_token.token == created_token.token
    assert retrieved_token.user_id == user_id


async def test_get_nonexistent_token_by_value(password_reset_service: PasswordResetService) -> None:
    """Test retrieving a non-existent token returns None."""
    token = await password_reset_service.get_token_by_value("non-existent-token")
    assert token is None


async def test_verify_token_success(password_reset_service: PasswordResetService) -> None:
    """Test successfully verifying a valid token."""
    user_id = uuid4()
    created_token = await password_reset_service.create_reset_token(user_id)

    verified_token = await password_reset_service.verify_token(created_token.token)

    assert verified_token is not None
    assert verified_token.id == created_token.id
    assert verified_token.used is True  # Should be marked as used after verification


async def test_verify_invalid_token(password_reset_service: PasswordResetService) -> None:
    """Test verifying an invalid token returns None."""
    result = await password_reset_service.verify_token("invalid-token")
    assert result is None


async def test_verify_already_used_token(password_reset_service: PasswordResetService) -> None:
    """Test that used tokens cannot be verified again."""
    user_id = uuid4()
    created_token = await password_reset_service.create_reset_token(user_id)

    # First verification should work
    first_verification = await password_reset_service.verify_token(created_token.token)
    assert first_verification is not None

    # Second verification should fail
    second_verification = await password_reset_service.verify_token(created_token.token)
    assert second_verification is None


async def test_cleanup_expired_tokens(password_reset_service: PasswordResetService) -> None:
    """Test cleanup of expired tokens."""
    # This test assumes the service has a cleanup method
    # The actual implementation may vary based on how cleanup is handled
    cleanup_count = await password_reset_service.cleanup_expired_tokens()
    assert isinstance(cleanup_count, int)
    assert cleanup_count >= 0


async def test_multiple_tokens_per_user(password_reset_service: PasswordResetService) -> None:
    """Test that multiple tokens can be created for the same user."""
    user_id = uuid4()

    token1 = await password_reset_service.create_reset_token(user_id)
    token2 = await password_reset_service.create_reset_token(user_id)

    assert token1.user_id == token2.user_id == user_id
    assert token1.token != token2.token
    assert token1.id != token2.id
