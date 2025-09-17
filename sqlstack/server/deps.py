"""Service dependencies for dependency injection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlspec.driver import AsyncDriverAdapterBase
from sqlstack.services import (
    EmailVerificationService,
    PasswordService,
    RoleService,
    TagService,
    TeamMemberService,
    TeamService,
    UserRoleService,
    UserService,
)

if TYPE_CHECKING:
    pass


def provide_users_service(db_session: AsyncDriverAdapterBase) -> UserService:
    """Provide user service with database driver.

    Args:
        db_session: The database session

    Returns:
        UserService instance
    """
    return UserService(db_session)


def provide_email_verification_service(db_session: AsyncDriverAdapterBase) -> EmailVerificationService:
    """Provide email verification service with database driver.

    Args:
        db_session: The database session

    Returns:
        EmailVerificationService instance
    """
    return EmailVerificationService(db_session)


def provide_password_service(db_session: AsyncDriverAdapterBase) -> PasswordService:
    """Provide password service with database driver.

    Args:
        db_session: The database session

    Returns:
        PasswordService instance
    """
    return PasswordService(db_session)


def provide_team_service(db_session: AsyncDriverAdapterBase) -> TeamService:
    """Provide team service with database driver.

    Args:
        db_session: The database session

    Returns:
        TeamService instance
    """
    return TeamService(db_session)


def provide_role_service(db_session: AsyncDriverAdapterBase) -> RoleService:
    """Provide role service with database driver.

    Args:
        db_session: The database session

    Returns:
        RoleService instance
    """
    return RoleService(db_session)


def provide_tag_service(db_session: AsyncDriverAdapterBase) -> TagService:
    """Provide tag service with database driver.

    Args:
        db_session: The database session

    Returns:
        TagService instance
    """
    return TagService(db_session)


def provide_team_member_service(db_session: AsyncDriverAdapterBase) -> TeamMemberService:
    """Provide team member service with database driver.

    Args:
        db_session: The database session

    Returns:
        TeamMemberService instance
    """
    return TeamMemberService(db_session)


def provide_user_role_service(db_session: AsyncDriverAdapterBase) -> UserRoleService:
    """Provide user role service with database driver.

    Args:
        db_session: The database session

    Returns:
        UserRoleService instance
    """
    return UserRoleService(db_session)
