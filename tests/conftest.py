# ruff: noqa: S106
"""Test configuration and fixtures for SQLStack."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

import pytest
from litestar.testing import AsyncTestClient

# Set test environment before any other imports
os.environ.update({
    "SECRET_KEY": "test-secret-key-for-testing-only",
    "DATABASE_URL": "postgresql+psycopg://test:test@localhost:5432/test_sqlstack",
    "DATABASE_ECHO": "false",
    "DATABASE_ECHO_POOL": "false",
    "LOG_LEVEL": "40",  # WARNING level as integer
    "EMAIL_ENABLED": "false",
})

from sqlstack import schemas as s
from sqlstack.services import (
    EmailVerificationService,
    PasswordResetService,
    RoleService,
    TagService,
    TeamService,
    UserService,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from litestar import Litestar
    from pytest import MonkeyPatch
    from pytest_databases.docker.postgres import PostgresService
    from sqlspec.adapters.asyncpg import AsyncpgConnection, AsyncpgDriver


pytestmark = pytest.mark.anyio
pytest_plugins = [
    "tests.data_fixtures",
    "pytest_databases.docker",
    "pytest_databases.docker.postgres",
]


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Set async backend for tests."""
    return "asyncio"


@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch: MonkeyPatch) -> None:
    """Patch the settings - environment already set at module level."""


@pytest.fixture(name="database_url")
async def fx_database_url(postgres_service: PostgresService) -> str:
    """PostgreSQL URL for testing."""
    return f"postgresql+psycopg://{postgres_service.user}:{postgres_service.password}@{postgres_service.host}:{postgres_service.port}/{postgres_service.database}"


@pytest.fixture(name="db_connection")
async def fx_db_connection(database_url: str) -> AsyncGenerator[AsyncpgConnection, None]:
    """Database connection for tests."""
    import asyncpg

    # Create connection
    conn = await asyncpg.connect(database_url.replace("postgresql+psycopg://", "postgresql://"))

    # Create tables if needed - this would normally be handled by migrations
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_account (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(255),
            password_hash VARCHAR(255),
            is_active BOOLEAN DEFAULT true,
            is_verified BOOLEAN DEFAULT false,
            is_superuser BOOLEAN DEFAULT false,
            avatar_url VARCHAR(500),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            last_login TIMESTAMP WITH TIME ZONE
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS role (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) UNIQUE NOT NULL,
            slug VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS tag (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) UNIQUE NOT NULL,
            slug VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS team (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            slug VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS email_verification_token (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
            email VARCHAR(255) NOT NULL,
            token VARCHAR(255) UNIQUE NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            used BOOLEAN DEFAULT false,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_token (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
            token VARCHAR(255) UNIQUE NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            used BOOLEAN DEFAULT false,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    yield conn

    # Cleanup
    await conn.execute("DROP TABLE IF EXISTS password_reset_token CASCADE")
    await conn.execute("DROP TABLE IF EXISTS email_verification_token CASCADE")
    await conn.execute("DROP TABLE IF EXISTS team CASCADE")
    await conn.execute("DROP TABLE IF EXISTS tag CASCADE")
    await conn.execute("DROP TABLE IF EXISTS role CASCADE")
    await conn.execute("DROP TABLE IF EXISTS user_account CASCADE")
    await conn.close()


@pytest.fixture(name="driver")
async def fx_driver(db_connection: AsyncpgConnection) -> AsyncpgDriver:
    """SQLSpec driver for tests."""
    from sqlspec.adapters.asyncpg import AsyncpgDriver

    return AsyncpgDriver(db_connection)


@pytest.fixture
def app() -> Litestar:
    """Create Litestar app for testing."""
    from sqlstack.server.asgi import create_app

    return create_app()


@pytest.fixture
async def client(app: Litestar) -> AsyncGenerator[AsyncTestClient, None]:
    """Create test client."""
    async with AsyncTestClient(app=app) as client:
        yield client


# Service fixtures
@pytest.fixture
async def user_service(driver: AsyncpgDriver) -> UserService:
    """Create UserService instance."""
    return UserService(driver)


@pytest.fixture
async def team_service(driver: AsyncpgDriver) -> TeamService:
    """Create TeamService instance."""
    return TeamService(driver)


@pytest.fixture
async def email_verification_service(driver: AsyncpgDriver) -> EmailVerificationService:
    """Create EmailVerificationService instance."""
    return EmailVerificationService(driver)


@pytest.fixture
async def password_reset_service(driver: AsyncpgDriver) -> PasswordResetService:
    """Create PasswordResetService instance."""
    return PasswordResetService(driver)


@pytest.fixture
async def role_service(driver: AsyncpgDriver) -> RoleService:
    """Create RoleService instance."""
    return RoleService(driver)


@pytest.fixture
async def tag_service(driver: AsyncpgDriver) -> TagService:
    """Create TagService instance."""
    return TagService(driver)


# Test data fixtures
@pytest.fixture
async def test_user(user_service: UserService) -> s.User:
    """Create a test user."""
    user_data = s.UserCreate(
        email="test@example.com",
        password="TestPassword123!",
        name="Test User",
        is_active=True,
        is_verified=True,
    )
    return await user_service.create(user_data)


@pytest.fixture
async def admin_user(user_service: UserService) -> s.User:
    """Create an admin user."""
    user_data = s.UserCreate(
        email="admin@example.com",
        password="AdminPassword123!",
        name="Admin User",
        is_active=True,
        is_verified=True,
        is_superuser=True,
    )
    return await user_service.create(user_data)


@pytest.fixture
async def unverified_user(user_service: UserService) -> s.User:
    """Create an unverified user."""
    user_data = s.UserCreate(
        email="unverified@example.com",
        password="TestPassword123!",
        name="Unverified User",
        is_active=True,
        is_verified=False,
    )
    return await user_service.create(user_data)


@pytest.fixture
async def test_role(role_service: RoleService) -> s.Role:
    """Create a test role."""
    role_data = s.RoleCreate(
        name="Test Role",
        slug="test-role",
        description="A test role for testing",
    )
    return await role_service.create(role_data)


@pytest.fixture
async def test_tag(tag_service: TagService) -> s.Tag:
    """Create a test tag."""
    tag_data = s.TagCreate(
        name="Test Tag",
        slug="test-tag",
        description="A test tag for testing",
    )
    return await tag_service.create(tag_data)


@pytest.fixture
async def test_team(team_service: TeamService, test_user: s.User) -> s.Team:
    """Create a test team with owner."""
    team_data = s.TeamCreate(
        name="Test Team",
        slug="test-team",
        description="A test team for integration testing",
        owner_id=test_user.id,
    )
    return await team_service.create(team_data)


@pytest.fixture
async def test_verification_token(
    email_verification_service: EmailVerificationService, unverified_user: s.User
) -> s.EmailVerificationToken:
    """Create a test email verification token."""
    return await email_verification_service.create_verification_token(unverified_user.id, unverified_user.email)


@pytest.fixture
async def test_password_reset_token(
    password_reset_service: PasswordResetService, test_user: s.User
) -> s.PasswordResetToken:
    """Create a test password reset token."""
    return await password_reset_service.create_reset_token(test_user.id)


@pytest.fixture
async def authenticated_client(client: AsyncTestClient, test_user: s.User) -> AsyncTestClient:
    """Create authenticated test client."""
    # Login and set auth headers
    login_response = await client.post(
        "/api/access/login",
        data={"username": test_user.email, "password": "TestPassword123!"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})

    return client


@pytest.fixture
async def admin_client(client: AsyncTestClient, admin_user: s.User) -> AsyncTestClient:
    """Create authenticated admin test client."""
    # Login as admin and set auth headers
    login_response = await client.post(
        "/api/access/login",
        data={"username": admin_user.email, "password": "AdminPassword123!"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})

    return client
