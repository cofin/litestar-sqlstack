"""Test configuration and fixtures for SQLStack."""

from __future__ import annotations

# Set test environment before any other imports
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
from litestar.testing import AsyncTestClient
from sqlspec.adapters.asyncpg import AsyncpgConfig

from sqlstack import schemas as s
from sqlstack.config import get_settings
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
    from sqlspec.adapters.asyncpg import AsyncpgDriver

pytestmark = pytest.mark.anyio
pytest_plugins = ["tests.data_fixtures", "pytest_databases.docker", "pytest_databases.docker.postgres"]


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Set async backend for tests."""
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def patch_settings(postgres_service: PostgresService, monkeypatch: MonkeyPatch) -> str:
    """Monkey patch settings to use test database URL.

    This fixture runs before any other fixtures and patches the cached settings
    object to use the test database connection details instead of loading from .env.
    """
    url = (
        f"postgresql://{postgres_service.user}:{postgres_service.password}"
        f"@{postgres_service.host}:{postgres_service.port}/{postgres_service.database}"
    )

    # Clear the settings cache to force reload
    get_settings.cache_clear()  # type: ignore[attr-defined]

    # Set environment variables before settings are loaded
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-testing-only")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("EMAIL_ENABLED", "false")

    # Force settings to reload with test environment
    settings = get_settings()

    # Verify the settings are using the test database
    assert url == settings.db.URL

    return url


@pytest.fixture(scope="session")
def database_url(patch_settings: str) -> str:
    """PostgreSQL URL for testing."""
    return patch_settings


@pytest.fixture(scope="session")
async def asyncpg_config(database_url: str) -> AsyncGenerator[AsyncpgConfig, None]:
    """Session-scoped test database configuration that runs migrations."""

    migration_path = Path(__file__).parent.parent / "sqlstack" / "db" / "migrations"

    config = AsyncpgConfig(
        pool_config={"dsn": database_url, "max_size": 15, "min_size": 5},
        extension_config={"litestar": {"commit_mode": "autocommit"}},
        migration_config={
            "script_location": str(migration_path),
            "version_table_name": "sqlspec_migrations_test",
            "extensions": ["litestar"],
        },
    )
    await config.migrate_up()

    yield config


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

    class DriverProxy:
        """Proxy that allows overriding driver methods in tests."""

        __slots__ = ("_driver", "_overrides")

        def __init__(self, wrapped: AsyncpgDriver) -> None:
            object.__setattr__(self, "_driver", wrapped)
            object.__setattr__(self, "_overrides", {})

        def __getattr__(self, name: str) -> Any:
            overrides: dict[str, Any] = object.__getattribute__(self, "_overrides")
            if name in overrides:
                return overrides[name]
            wrapped: AsyncpgDriver = object.__getattribute__(self, "_driver")
            return getattr(wrapped, name)

        def __setattr__(self, name: str, value: Any) -> None:
            if name in {"_driver", "_overrides"}:
                object.__setattr__(self, name, value)
                return
            overrides: dict[str, Any] = object.__getattribute__(self, "_overrides")
            overrides[name] = value

        def __delattr__(self, name: str) -> None:
            overrides: dict[str, Any] = object.__getattribute__(self, "_overrides")
            if name in overrides:
                del overrides[name]
                return
            wrapped: AsyncpgDriver = object.__getattribute__(self, "_driver")
            delattr(wrapped, name)

        @property
        def __wrapped__(self) -> AsyncpgDriver:
            return cast("AsyncpgDriver", object.__getattribute__(self, "_driver"))

    async with asyncpg_config.provide_session() as raw_driver:
        yield cast("AsyncpgDriver", DriverProxy(raw_driver))


@pytest.fixture
def app(asyncpg_config: AsyncpgConfig, monkeypatch: MonkeyPatch) -> Litestar:
    """Litestar app fixture with test database configuration.

    Recreates the SQLSpec config to point to test database.
    The asyncpg_config fixture already ran migrations on the test database.
    """

    from sqlstack.server.asgi import create_app

    return create_app()


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
        email="test@example.com", password="TestPassword123!", name="Test User", is_active=True, is_verified=True
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
async def superuser(admin_user: s.User) -> s.User:
    """Alias for admin user when a superuser is required."""
    return admin_user


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
    role_data = s.RoleCreate(name="Test Role", description="A test role for testing")
    return await role_service.create_role(role_data)


@pytest.fixture
async def test_tag(tag_service: TagService) -> s.Tag:
    """Create a test tag."""
    tag_data = s.TagCreate(name="Test Tag", description="A test tag for testing")
    return await tag_service.create_tag(tag_data)


@pytest.fixture
async def test_team(team_service: TeamService, test_user: s.User) -> s.Team:
    """Create a test team with owner."""
    team_data = s.TeamCreate(name="Test Team", description="A test team for integration testing")
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


@pytest.fixture
async def authenticated_headers(
    request: pytest.FixtureRequest, client: AsyncTestClient, test_user: s.User, admin_user: s.User
) -> dict[str, str]:
    """Create authentication headers for different user types.

    Usage:
        @pytest.mark.parametrize("authenticated_headers", ["user"], indirect=True)
        async def test_something(client: AsyncTestClient, authenticated_headers: dict[str, str]):
            response = await client.get("/api/endpoint", headers=authenticated_headers)
    """
    user_type = request.param if hasattr(request, "param") else "user"

    if user_type == "superuser":
        email = admin_user.email
        password = "AdminPassword123!"
    else:  # user
        email = test_user.email
        password = "TestPassword123!"

    # Login and get token
    login_response = await client.post(
        "/api/access/login",
        data={"username": email, "password": password},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return {}
