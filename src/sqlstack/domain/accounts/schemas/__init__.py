"""Account domain schemas.

Provides schemas for user accounts, roles, authentication, and related operations.
"""

from sqlstack.domain.accounts.schemas._auth import AccountLogin, AccountRegister
from sqlstack.domain.accounts.schemas._password import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    PasswordResetToken,
    PasswordStrengthAnalysis,
    PasswordUpdate,
    PasswordVerify,
    ResetPasswordRequest,
    ResetPasswordResponse,
    ValidateResetTokenRequest,
    ValidateResetTokenResponse,
)
from sqlstack.domain.accounts.schemas._roles import (
    Role,
    RoleCreate,
    RoleUpdate,
    UserRole,
    UserRoleAdd,
    UserRoleCreate,
    UserRoleRevoke,
)
from sqlstack.domain.accounts.schemas._user import ProfileUpdate, User, UserCreate, UserUpdate

__all__ = (
    "AccountLogin",
    "AccountRegister",
    "ForgotPasswordRequest",
    "ForgotPasswordResponse",
    "PasswordResetToken",
    "PasswordStrengthAnalysis",
    "PasswordUpdate",
    "PasswordVerify",
    "ProfileUpdate",
    "ResetPasswordRequest",
    "ResetPasswordResponse",
    "Role",
    "RoleCreate",
    "RoleUpdate",
    "User",
    "UserCreate",
    "UserRole",
    "UserRoleAdd",
    "UserRoleCreate",
    "UserRoleRevoke",
    "UserUpdate",
    "ValidateResetTokenRequest",
    "ValidateResetTokenResponse",
)
