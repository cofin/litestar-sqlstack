from datetime import datetime
from typing import Any
from uuid import UUID

from sqlstack.lib.schema import CamelizedBaseStruct
from sqlstack.lib.types import Password

__all__ = (
    "ForgotPasswordRequest",
    "ForgotPasswordResponse",
    "PasswordResetToken",
    "PasswordStrengthAnalysis",
    "PasswordUpdate",
    "PasswordVerify",
    "ResetPasswordRequest",
    "ResetPasswordResponse",
    "ValidateResetTokenRequest",
    "ValidateResetTokenResponse",
)


class PasswordUpdate(CamelizedBaseStruct):
    current_password: Password
    new_password: Password


class PasswordVerify(CamelizedBaseStruct):
    current_password: Password


class ForgotPasswordRequest(CamelizedBaseStruct):
    """Request schema for initiating password reset."""

    email: str


class ForgotPasswordResponse(CamelizedBaseStruct):
    """Response schema for password reset request."""

    message: str
    expires_in: int = 3600  # 1 hour in seconds


class ValidateResetTokenRequest(CamelizedBaseStruct):
    """Request schema for validating a reset token."""

    token: str


class ValidateResetTokenResponse(CamelizedBaseStruct):
    """Response schema for token validation."""

    valid: bool
    user_id: UUID | None = None
    expires_at: datetime | None = None


class ResetPasswordRequest(CamelizedBaseStruct):
    """Request schema for resetting password with token."""

    token: str
    password: str
    confirm_password: str

    def __post_init__(self) -> None:
        if self.password != self.confirm_password:
            msg = "Passwords do not match"
            raise ValueError(msg)


class ResetPasswordResponse(CamelizedBaseStruct):
    """Response schema for successful password reset."""

    message: str
    user_id: UUID


class PasswordResetToken(CamelizedBaseStruct):
    """Password reset token model."""

    id: UUID
    user_id: UUID
    token: str
    expires_at: datetime
    used: bool = False


class PasswordStrengthAnalysis(CamelizedBaseStruct):
    """Password strength analysis response."""

    score: int
    strength: str
    requirements: dict[str, Any]
    feedback: list[str]
