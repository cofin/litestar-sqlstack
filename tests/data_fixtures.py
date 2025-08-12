"""Data fixtures for SQLStack tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from litestar import Litestar
    from pytest import MonkeyPatch

pytestmark = pytest.mark.anyio


@pytest.fixture(name="app")
def fx_app(pytestconfig: pytest.Config, monkeypatch: MonkeyPatch) -> Litestar:
    """App fixture.

    Returns:
        An application instance, configured via plugin.
    """
    from sqlstack.server.asgi import create_app

    return create_app()


@pytest.fixture(name="raw_users")
def fx_raw_users() -> list[dict[str, Any]]:
    """Unstructured user representations."""
    return [
        {
            "id": "97108ac1-ffcb-411d-8b1e-d9183399f63b",
            "email": "superuser@example.com",
            "name": "Super User",
            "password": "Test_Password1!",
            "is_superuser": True,
            "is_active": True,
            "is_verified": True,
        },
        {
            "id": "5ef29f3c-3560-4d15-ba6b-a2e5c721e4d2",
            "email": "user@example.com",
            "name": "Example User",
            "password": "Test_Password2!",
            "is_superuser": False,
            "is_active": True,
            "is_verified": True,
        },
        {
            "id": "5ef29f3c-3560-4d15-ba6b-a2e5c721e999",
            "email": "inactive@example.com",
            "name": "Inactive User",
            "password": "Test_Password3!",
            "is_superuser": False,
            "is_active": False,
            "is_verified": False,
        },
    ]


@pytest.fixture(name="raw_teams")
def fx_raw_teams() -> list[dict[str, Any]]:
    """Unstructured team representations."""
    return [
        {
            "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "name": "Test Team Alpha",
            "slug": "test-team-alpha",
            "description": "First test team for integration testing",
        },
        {
            "id": "f47ac10b-58cc-4372-a567-0e02b2c3d480",
            "name": "Test Team Beta",
            "slug": "test-team-beta",
            "description": "Second test team for integration testing",
        },
    ]


@pytest.fixture(name="raw_roles")
def fx_raw_roles() -> list[dict[str, Any]]:
    """Unstructured role representations."""
    return [
        {
            "id": "a47ac10b-58cc-4372-a567-0e02b2c3d479",
            "name": "Admin",
            "slug": "admin",
            "description": "Administrator role with full access",
        },
        {
            "id": "b47ac10b-58cc-4372-a567-0e02b2c3d479",
            "name": "User",
            "slug": "user",
            "description": "Standard user role with limited access",
        },
        {
            "id": "c47ac10b-58cc-4372-a567-0e02b2c3d479",
            "name": "Viewer",
            "slug": "viewer",
            "description": "Read-only access role",
        },
    ]


@pytest.fixture(name="raw_tags")
def fx_raw_tags() -> list[dict[str, Any]]:
    """Unstructured tag representations."""
    return [
        {
            "id": "d47ac10b-58cc-4372-a567-0e02b2c3d479",
            "name": "Frontend",
            "slug": "frontend",
            "description": "Frontend development related",
        },
        {
            "id": "e47ac10b-58cc-4372-a567-0e02b2c3d479",
            "name": "Backend",
            "slug": "backend",
            "description": "Backend development related",
        },
        {
            "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "name": "Testing",
            "slug": "testing",
            "description": "Testing and QA related",
        },
    ]
