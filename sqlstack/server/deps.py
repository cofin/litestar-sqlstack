"""Service dependencies for dependency injection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlstack.services import (
    EmailVerificationService,
    PasswordResetService,
    RoleService,
    TagService,
    TeamInvitationService,
    TeamMemberService,
    TeamService,
    UserOAuthAccountService,
    UserRoleService,
    UserService,
)

if TYPE_CHECKING:
    from sqlspec.adapters.asyncpg import AsyncpgDriver


def provide_users_service(db_session: AsyncpgDriver) -> UserService:
    """Provide user service with database driver.

    Args:
        db_session: The database session

    Returns:
        UserService instance
    """
    return UserService(db_session)


def provide_email_verification_service(db_session: AsyncpgDriver) -> EmailVerificationService:
    """Provide email verification service with database driver.

    Args:
        db_session: The database session

    Returns:
        EmailVerificationService instance
    """
    return EmailVerificationService(db_session)


def provide_password_reset_service(db_session: AsyncpgDriver) -> PasswordResetService:
    """Provide password reset service with database driver.

    Args:
        db_session: The database session

    Returns:
        PasswordResetService instance
    """
    return PasswordResetService(db_session)


def provide_team_service(db_session: AsyncpgDriver) -> TeamService:
    """Provide team service with database driver.

    Args:
        db_session: The database session

    Returns:
        TeamService instance
    """
    return TeamService(db_session)


def provide_role_service(db_session: AsyncpgDriver) -> RoleService:
    """Provide role service with database driver.

    Args:
        db_session: The database session

    Returns:
        RoleService instance
    """
    return RoleService(db_session)


def provide_tag_service(db_session: AsyncpgDriver) -> TagService:
    """Provide tag service with database driver.

    Args:
        db_session: The database session

    Returns:
        TagService instance
    """
    return TagService(db_session)


def provide_team_invitation_service(db_session: AsyncpgDriver) -> TeamInvitationService:
    """Provide team invitation service with database driver.

    Args:
        db_session: The database session

    Returns:
        TeamInvitationService instance
    """
    return TeamInvitationService(db_session)


def provide_team_member_service(db_session: AsyncpgDriver) -> TeamMemberService:
    """Provide team member service with database driver.

    Args:
        db_session: The database session

    Returns:
        TeamMemberService instance
    """
    return TeamMemberService(db_session)


def provide_user_oauth_service(db_session: AsyncpgDriver) -> UserOAuthAccountService:
    """Provide user OAuth account service with database driver.

    Args:
        db_session: The database session

    Returns:
        UserOAuthAccountService instance
    """
    return UserOAuthAccountService(db_session)


def provide_user_role_service(db_session: AsyncpgDriver) -> UserRoleService:
    """Provide user role service with database driver.

    Args:
        db_session: The database session

    Returns:
        UserRoleService instance
    """
    return UserRoleService(db_session)


# Plural provider aliases for backward compatibility
def provide_teams_service(db_session: AsyncpgDriver) -> TeamService:
    """Provide teams service (alias for team service)."""
    return provide_team_service(db_session)


def provide_roles_service(db_session: AsyncpgDriver) -> RoleService:
    """Provide roles service (alias for role service)."""
    return provide_role_service(db_session)


def provide_tags_service(db_session: AsyncpgDriver) -> TagService:
    """Provide tags service (alias for tag service)."""
    return provide_tag_service(db_session)
