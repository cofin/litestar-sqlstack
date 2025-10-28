"""Test configuration and fixtures for SQLStack."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from litestar.testing import AsyncTestClient

# Set test environment before any other imports
os.environ.update(
    {
        "SECRET_KEY": "test-secret-key-for-testing-only",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test_sqlstack",
        "DATABASE_ECHO": "false",
        "DATABASE_ECHO_POOL": "false",
        "LOG_LEVEL": "40",  # WARNING level as integer
        "EMAIL_ENABLED": "false",
    }
)

from sqlstack import schemas as s
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
    from collections.abc import AsyncGenerator

    from litestar import Litestar
    from pytest import MonkeyPatch
    from pytest_databases.docker.postgres import PostgresService
    from sqlspec.adapters.asyncpg import AsyncpgConfig, AsyncpgDriver

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


@pytest.fixture(scope="session")
def database_url(postgres_service: PostgresService) -> str:
    """PostgreSQL URL for testing."""
    return (
        f"postgresql://{postgres_service.user}:{postgres_service.password}"
        f"@{postgres_service.host}:{postgres_service.port}/{postgres_service.database}"
    )


@pytest.fixture(scope="session")
async def asyncpg_config(database_url: str) -> AsyncGenerator[AsyncpgConfig, None]:
    """Session-scoped test database configuration that runs migrations."""
    from sqlspec.adapters.asyncpg import AsyncpgConfig
    from sqlspec.migrations.commands import AsyncMigrationCommands

    migration_path = Path(__file__).parent.parent / "sqlstack" / "db" / "migrations"

    config = AsyncpgConfig(
        pool_config={"dsn": database_url, "max_size": 15, "min_size": 5},
        migration_config={
            "script_location": str(migration_path),
            "version_table_name": "sqlspec_migrations_test",
        },
    )

    # Run migrations to set up schema
    migration_commands = AsyncMigrationCommands(config)
    await migration_commands.upgrade("head")

    yield config

    # Cleanup: optionally downgrade migrations
    # await migration_commands.downgrade("base")


@pytest.fixture(autouse=True)
async def clean_database(asyncpg_config: AsyncpgConfig) -> AsyncGenerator[None, None]:
    """Function-scoped fixture to truncate all tables for test isolation.

    Uses dynamic query to discover all tables in public schema,
    excluding the migration version table.
    """
    yield  # Run test first

    # Clean up after test
    async with asyncpg_config.provide_session() as driver:
        await driver.execute("""
            DO $$
            DECLARE stmt text;
            BEGIN
                SELECT 'TRUNCATE TABLE ' ||
                       string_agg(format('%I.%I', schemaname, tablename), ', ') ||
                       ' RESTART IDENTITY CASCADE'
                INTO stmt
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename NOT IN ('sqlspec_migrations_test');

                IF stmt IS NOT NULL THEN
                    EXECUTE stmt;
                END IF;
            END $$;
        """)
        await driver.commit()


@pytest.fixture
async def driver(asyncpg_config: AsyncpgConfig) -> AsyncGenerator[AsyncpgDriver, None]:
    """Function-scoped SQLSpec driver for tests."""
    async with asyncpg_config.provide_session() as driver:
        yield driver


@pytest.fixture
def app(asyncpg_config: AsyncpgConfig, database_url: str, monkeypatch: MonkeyPatch) -> Litestar:
    """Litestar app fixture with test database configuration.

    Recreates the SQLSpec config to point to test database.
    The asyncpg_config fixture already ran migrations on the test database.
    """
    import os
    import sys

    # Remove app config module to force reload
    if "sqlstack.config" in sys.modules:
        del sys.modules["sqlstack.config"]
    if "sqlstack.server.asgi" in sys.modules:
        del sys.modules["sqlstack.server.asgi"]

    # Temporarily set env vars for config initialization
    original_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    os.environ["POOL_MIN_SIZE"] = "5"
    os.environ["POOL_MAX_SIZE"] = "15"
    os.environ["MIGRATION_DDL_VERSION_TABLE"] = "sqlspec_migrations_test"

    try:
        from sqlstack.server.asgi import create_app

        return create_app()
    finally:
        # Restore original env
        if original_url:
            os.environ["DATABASE_URL"] = original_url


@pytest.fixture
async def client(app: Litestar) -> AsyncGenerator[AsyncTestClient, None]:
    """Function-scoped test client."""
    async with AsyncTestClient(app=app) as client:
        yield client


# Service fixtures
@pytest.fixture
def user_service(driver: AsyncpgDriver) -> UserService:
    """Create UserService instance."""
    return UserService(driver)


@pytest.fixture
def team_service(driver: AsyncpgDriver) -> TeamService:
    """Create TeamService instance."""
    return TeamService(driver)


@pytest.fixture
def email_verification_service(driver: AsyncpgDriver) -> EmailVerificationService:
    """Create EmailVerificationService instance."""
    return EmailVerificationService(driver)


@pytest.fixture
def password_service(driver: AsyncpgDriver) -> PasswordService:
    """Create PasswordService instance."""
    return PasswordService(driver)


@pytest.fixture
def role_service(driver: AsyncpgDriver) -> RoleService:
    """Create RoleService instance."""
    return RoleService(driver)


@pytest.fixture
def tag_service(driver: AsyncpgDriver) -> TagService:
    """Create TagService instance."""
    return TagService(driver)


@pytest.fixture
def team_member_service(driver: AsyncpgDriver) -> TeamMemberService:
    """Create TeamMemberService instance."""
    return TeamMemberService(driver)


@pytest.fixture
def user_role_service(driver: AsyncpgDriver) -> UserRoleService:
    """Create UserRoleService instance."""
    return UserRoleService(driver)


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
    return await user_service.create_user(user_data)


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
    return await user_service.create_user(user_data)


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
    return await user_service.create_user(user_data)


@pytest.fixture
async def test_role(role_service: RoleService) -> s.Role:
    """Create a test role."""
    role_data = s.RoleCreate(
        name="Test Role",
        description="A test role for testing",
    )
    return await role_service.create_role(role_data)


@pytest.fixture
async def test_tag(tag_service: TagService) -> s.Tag:
    """Create a test tag."""
    tag_data = s.TagCreate(
        name="Test Tag",
        description="A test tag for testing",
    )
    return await tag_service.create_tag(tag_data)


@pytest.fixture
async def test_team(team_service: TeamService, test_user: s.User) -> s.Team:
    """Create a test team with owner."""
    team_data = s.TeamCreate(
        name="Test Team",
        description="A test team for integration testing",
    )
    return await team_service.create(team_data)


@pytest.fixture
async def test_verification_token(
    email_verification_service: EmailVerificationService, unverified_user: s.User
) -> s.EmailVerificationToken:
    """Create a test email verification token."""
    return await email_verification_service.create_verification_token(unverified_user.id, unverified_user.email)


@pytest.fixture
async def test_password_reset_token(password_service: PasswordService, test_user: s.User) -> s.PasswordResetToken:
    """Create a test password reset token."""
    return await password_service.create_reset_token(test_user.id)


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
