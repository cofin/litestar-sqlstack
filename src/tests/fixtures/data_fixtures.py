"""Data fixtures for SQLStack tests."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.anyio


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
