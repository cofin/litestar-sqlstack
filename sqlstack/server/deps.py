"""Service dependencies for dependency injection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlspec.adapters.asyncpg import AsyncpgDriver

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
    from litestar import Request
    from sqlspec.adapters.asyncpg import AsyncpgConnection


def _get_db_session(request: Request) -> AsyncpgConnection:
    """Get database session from request state.

    Args:
        request: The Litestar request object

    Returns:
        Database session/connection
    """
    # This will be provided by the SQLSpec Litestar plugin
    return request.state.session


def provide_users_service(request: Request) -> UserService:
    """Provide user service with database driver.

    Args:
        request: The Litestar request object

    Returns:
        UserService instance
    """
    session = _get_db_session(request)
    driver = AsyncpgDriver(session)
    return UserService(driver)


def provide_email_verification_service(request: Request) -> EmailVerificationService:
    """Provide email verification service with database driver.

    Args:
        request: The Litestar request object

    Returns:
        EmailVerificationService instance
    """
    session = _get_db_session(request)
    driver = AsyncpgDriver(session)
    return EmailVerificationService(driver)


def provide_password_reset_service(request: Request) -> PasswordResetService:
    """Provide password reset service with database driver.

    Args:
        request: The Litestar request object

    Returns:
        PasswordResetService instance
    """
    session = _get_db_session(request)
    driver = AsyncpgDriver(session)
    return PasswordResetService(driver)


def provide_team_service(request: Request) -> TeamService:
    """Provide team service with database driver.

    Args:
        request: The Litestar request object

    Returns:
        TeamService instance
    """
    session = _get_db_session(request)
    driver = AsyncpgDriver(session)
    return TeamService(driver)


def provide_role_service(request: Request) -> RoleService:
    """Provide role service with database driver.

    Args:
        request: The Litestar request object

    Returns:
        RoleService instance
    """
    session = _get_db_session(request)
    driver = AsyncpgDriver(session)
    return RoleService(driver)


def provide_tag_service(request: Request) -> TagService:
    """Provide tag service with database driver.

    Args:
        request: The Litestar request object

    Returns:
        TagService instance
    """
    session = _get_db_session(request)
    driver = AsyncpgDriver(session)
    return TagService(driver)


def provide_team_invitation_service(request: Request) -> TeamInvitationService:
    """Provide team invitation service with database driver.

    Args:
        request: The Litestar request object

    Returns:
        TeamInvitationService instance
    """
    session = _get_db_session(request)
    driver = AsyncpgDriver(session)
    return TeamInvitationService(driver)


def provide_team_member_service(request: Request) -> TeamMemberService:
    """Provide team member service with database driver.

    Args:
        request: The Litestar request object

    Returns:
        TeamMemberService instance
    """
    session = _get_db_session(request)
    driver = AsyncpgDriver(session)
    return TeamMemberService(driver)


def provide_user_oauth_service(request: Request) -> UserOAuthAccountService:
    """Provide user OAuth account service with database driver.

    Args:
        request: The Litestar request object

    Returns:
        UserOAuthAccountService instance
    """
    session = _get_db_session(request)
    driver = AsyncpgDriver(session)
    return UserOAuthAccountService(driver)


def provide_user_role_service(request: Request) -> UserRoleService:
    """Provide user role service with database driver.

    Args:
        request: The Litestar request object

    Returns:
        UserRoleService instance
    """
    session = _get_db_session(request)
    driver = AsyncpgDriver(session)
    return UserRoleService(driver)


# Plural provider aliases for backward compatibility
def provide_teams_service(request: Request) -> TeamService:
    """Provide teams service (alias for team service)."""
    return provide_team_service(request)


def provide_roles_service(request: Request) -> RoleService:
    """Provide roles service (alias for role service)."""
    return provide_role_service(request)


def provide_tags_service(request: Request) -> TagService:
    """Provide tags service (alias for tag service)."""
    return provide_tag_service(request)
