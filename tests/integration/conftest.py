"""Integration test configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from sqlstack.lib.crypt import get_password_hash
from sqlstack.services import (
    RoleService,
    TeamService,
    UserService,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from litestar import Litestar
    from litestar.testing import AsyncTestClient
    from pytest import MonkeyPatch
    from pytest_databases.docker.postgres import PostgresService
    from sqlspec.adapters.asyncpg import AsyncpgDriver

    from sqlstack import schemas as s

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
async def _seed_integration_db(
    postgres_service: PostgresService,
    driver: AsyncpgDriver,
    app: Litestar,
    monkeypatch: MonkeyPatch,
) -> AsyncGenerator[None, None]:
    """Seed database for integration tests following reference app pattern."""
    import asyncpg

    from sqlstack.config import get_database_config

    # Create connection using postgres_service directly (like reference app)
    database_url = f"postgresql://{postgres_service.user}:{postgres_service.password}@{postgres_service.host}:{postgres_service.port}/{postgres_service.database}"
    conn = await asyncpg.connect(database_url)

    # Patch the database config to use our test connection
    test_config = get_database_config()
    test_config.url = database_url
    monkeypatch.setattr("sqlstack.config._DATABASE_CONFIG", test_config)

    # Create test users with hashed passwords
    test_user_id = uuid4()
    admin_user_id = uuid4()

    # Create default role first
    await conn.execute(
        """
        INSERT INTO role (id, name, slug, description)
        VALUES ($1, 'User', 'user', 'Default user role')
        ON CONFLICT (slug) DO NOTHING
    """,
        uuid4(),
    )

    # Create test users
    await conn.execute(
        """
        INSERT INTO user_account (id, email, name, password_hash, is_active, is_verified, is_superuser)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (email) DO UPDATE SET
            name = EXCLUDED.name,
            password_hash = EXCLUDED.password_hash,
            is_active = EXCLUDED.is_active,
            is_verified = EXCLUDED.is_verified,
            is_superuser = EXCLUDED.is_superuser
    """,
        test_user_id,
        "test@example.com",
        "Test User",
        get_password_hash("TestPassword123!"),
        True,
        True,
        False,
    )

    await conn.execute(
        """
        INSERT INTO user_account (id, email, name, password_hash, is_active, is_verified, is_superuser)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (email) DO UPDATE SET
            name = EXCLUDED.name,
            password_hash = EXCLUDED.password_hash,
            is_active = EXCLUDED.is_active,
            is_verified = EXCLUDED.is_verified,
            is_superuser = EXCLUDED.is_superuser
    """,
        admin_user_id,
        "admin@example.com",
        "Admin User",
        get_password_hash("AdminPassword123!"),
        True,
        True,
        True,
    )

    await conn.close()

    yield

    # Cleanup after tests
    conn = await asyncpg.connect(database_url)

    # Clean tables in reverse dependency order
    cleanup_tables = [
        "password_reset_token",
        "email_verification_token",
        "team",
        "tag",
        "role",
        "user_account",
    ]

    for table in cleanup_tables:
        # NOTE: Table names are safe constants - no user input
        await conn.execute(f"DELETE FROM {table}")  # noqa: S608

    await conn.close()


@pytest.fixture(autouse=True)
def _patch_db_config(
    app: Litestar,
    postgres_service: PostgresService,
    monkeypatch: MonkeyPatch,
) -> None:
    """Patch database configuration for integration tests."""
    from sqlstack import config

    database_url = f"postgresql+asyncpg://{postgres_service.user}:{postgres_service.password}@{postgres_service.host}:{postgres_service.port}/{postgres_service.database}"

    # Update the database config
    test_config = config.get_database_config()
    test_config.url = database_url
    monkeypatch.setattr("sqlstack.config._DATABASE_CONFIG", test_config)


@pytest.fixture
async def authenticated_headers(
    request: pytest.FixtureRequest,
    client: AsyncTestClient,
    test_user: s.User,
    admin_user: s.User,
) -> dict[str, str]:
    """Create authenticated headers based on user_type parameter."""
    user_type = getattr(request, "param", "user")

    if user_type == "superuser":
        user = admin_user
        password = "AdminPassword123!"
    else:
        user = test_user
        password = "TestPassword123!"

    # Login and get token
    login_response = await client.post(
        "/api/access/login",
        data={"username": user.email, "password": password},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    if login_response.status_code != 200:
        error_msg = f"Login failed: {login_response.status_code} - {login_response.text}"
        raise RuntimeError(error_msg)

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def integration_user_service(driver: AsyncpgDriver) -> AsyncGenerator[UserService, None]:
    """Create UserService instance for integration tests."""
    service = UserService(driver)
    yield service


@pytest.fixture
async def integration_team_service(driver: AsyncpgDriver) -> AsyncGenerator[TeamService, None]:
    """Create TeamService instance for integration tests."""
    service = TeamService(driver)
    yield service


@pytest.fixture
async def integration_role_service(driver: AsyncpgDriver) -> AsyncGenerator[RoleService, None]:
    """Create RoleService instance for integration tests."""
    service = RoleService(driver)
    yield service


@pytest.fixture
async def test_user_headers(client: AsyncTestClient) -> dict[str, str]:
    """Get authentication headers for test user."""
    login_response = await client.post(
        "/api/access/login",
        data={"username": "test@example.com", "password": "TestPassword123!"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    if login_response.status_code != 200:
        error_msg = f"Login failed: {login_response.status_code} - {login_response.text}"
        raise RuntimeError(error_msg)

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def superuser_headers(client: AsyncTestClient) -> dict[str, str]:
    """Get authentication headers for superuser."""
    login_response = await client.post(
        "/api/access/login",
        data={"username": "admin@example.com", "password": "AdminPassword123!"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    if login_response.status_code != 200:
        error_msg = f"Login failed: {login_response.status_code} - {login_response.text}"
        raise RuntimeError(error_msg)

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
