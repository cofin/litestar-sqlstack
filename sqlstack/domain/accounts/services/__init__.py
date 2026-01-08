"""Account domain services.

Provides services for user accounts, roles, authentication, and related operations.
"""

from sqlstack.domain.accounts.services._email_verification import EmailVerificationService
from sqlstack.domain.accounts.services._password import PasswordService, PasswordValidationError
from sqlstack.domain.accounts.services._role import RoleService
from sqlstack.domain.accounts.services._user import UserService
from sqlstack.domain.accounts.services._user_role import UserRoleService
from sqlstack.domain.accounts.services._user_oauth_account import UserOAuthAccountService

__all__ = (
    "EmailVerificationService",
    "PasswordService",
    "RoleService",
    "UserRoleService",
    "UserService",
    "UserOAuthAccountService",
)
