from datetime import datetime
from uuid import UUID

from sqlstack.lib.schema import CamelizedBaseStruct

__all__ = (
    "EmailVerificationConfirm",
    "EmailVerificationRequest",
    "EmailVerificationResponse",
    "EmailVerificationStatusResponse",
    "EmailVerificationToken",
)


class EmailVerificationRequest(CamelizedBaseStruct):
    """Request schema for email verification."""

    email: str


class EmailVerificationConfirm(CamelizedBaseStruct):
    """Schema for confirming email verification with token."""

    token: str


class EmailVerificationResponse(CamelizedBaseStruct):
    """Response schema for email verification request."""

    message: str
    expires_in: int = 86400  # 24 hours in seconds


class EmailVerificationStatusResponse(CamelizedBaseStruct):
    """Response schema for email verification status."""

    user_id: UUID
    email: str
    is_verified: bool


class EmailVerificationToken(CamelizedBaseStruct):
    """Email verification token model."""

    id: UUID
    user_id: UUID
    email: str
    token: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    used: bool = False
