"""Integration test configuration and fixtures that require external services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest
from litestar.testing import AsyncTestClient

from sqlstack.config import get_settings
from sqlstack.domain.accounts import schemas as s
from sqlstack.domain.accounts.services import PasswordService, RoleService, UserRoleService, UserService
from sqlstack.lib.settings import Settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from litestar import Litestar
    from pytest_databases.docker.postgres import PostgresService
    from sqlspec.adapters.asyncpg import AsyncpgConfig, AsyncpgDriver


@pytest.fixture(scope="session", autouse=True)
def database_url(postgres_service: PostgresService) -> Generator[str, None, None]:
    """Monkey patch settings to use test database URL.

    This fixture runs before any other fixtures and patches the cached settings
    object to use the test database connection details instead of loading from .env.
    """
    import os

    url = (
        f"postgresql://{postgres_service.user}:{postgres_service.password}"
        f"@{postgres_service.host}:{postgres_service.port}/{postgres_service.database}"
    )

    original_env = {
        "SECRET_KEY": os.environ.get("SECRET_KEY"),
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "EMAIL_ENABLED": os.environ.get("EMAIL_ENABLED"),
    }

    Settings.from_env.cache_clear()  # type: ignore[attr-defined]

    os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
    os.environ["DATABASE_URL"] = url
    os.environ["EMAIL_ENABLED"] = "false"

    settings = get_settings()
    assert url == settings.db.URL

    yield url

    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture(scope="session")
async def asyncpg_config(database_url: str) -> AsyncGenerator[AsyncpgConfig, None]:
    """Session-scoped test database configuration that runs migrations."""

    settings = get_settings()

    config = settings.db.get_config()
    await config.migrate_up()

    yield config


@pytest.fixture
async def clean_database(asyncpg_config: AsyncpgConfig) -> AsyncGenerator[None, None]:
    """Function-scoped fixture to truncate all tables for test isolation."""

    yield

    async with asyncpg_config.provide_session() as driver:
        await driver.execute(
            """
            DO $$
            DECLARE stmt text;
            BEGIN
                SELECT 'TRUNCATE TABLE ' ||
                       string_agg(format('%I.%I', schemaname, tablename), ', ') ||
                       ' RESTART IDENTITY CASCADE'
                INTO stmt
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename NOT IN ('ddl_version');

                IF stmt IS NOT NULL THEN
                    EXECUTE stmt;
                END IF;
            END $$;
            """
        )
        await driver.commit()


@pytest.fixture
async def driver(asyncpg_config: AsyncpgConfig) -> AsyncGenerator[AsyncpgDriver, None]:
    """Function-scoped SQLSpec driver for tests."""

    class DriverProxy:
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
def app(asyncpg_config: AsyncpgConfig) -> Litestar:
    """Litestar app fixture with test database configuration."""

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
    return UserService(driver)


@pytest.fixture
def email_verification_service(driver: AsyncpgDriver) -> EmailVerificationService:
    return EmailVerificationService(driver)


@pytest.fixture
def password_service(driver: AsyncpgDriver) -> PasswordService:
    return PasswordService(driver)


@pytest.fixture
def role_service(driver: AsyncpgDriver) -> RoleService:
    return RoleService(driver)


@pytest.fixture
def user_role_service(driver: AsyncpgDriver) -> UserRoleService:
    return UserRoleService(driver)


@pytest.fixture
async def test_user(user_service: UserService) -> s.User:
    user_data = s.UserCreate(
        email="test@example.com", password="TestPassword123!", name="Test User", is_active=True, is_verified=True
    )
    return await user_service.create_user(user_data)


@pytest.fixture
async def admin_user(user_service: UserService) -> s.User:
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
    return admin_user


@pytest.fixture
async def unverified_user(user_service: UserService) -> s.User:
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
    role_data = s.RoleCreate(name="Test Role", description="A test role for testing")
    return await role_service.create_role(role_data)


@pytest.fixture
async def test_verification_token(
    email_verification_service: EmailVerificationService, unverified_user: s.User
) -> s.EmailVerificationToken:
    return await email_verification_service.create_verification_token(unverified_user.id, unverified_user.email)


@pytest.fixture
async def test_password_reset_token(password_service: PasswordService, test_user: s.User) -> s.PasswordResetToken:
    return await password_service.create_reset_token(test_user.id)


@pytest.fixture
async def authenticated_client(client: AsyncTestClient, test_user: s.User) -> AsyncTestClient:
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
    user_type = request.param if hasattr(request, "param") else "user"

    if user_type == "superuser":
        email = admin_user.email
        password = "AdminPassword123!"
    else:
        email = test_user.email
        password = "TestPassword123!"

    login_response = await client.post(
        "/api/access/login",
        data={"username": email, "password": password},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    login_response.raise_for_status()
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
