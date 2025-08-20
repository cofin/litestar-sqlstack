"""Unit test configuration."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def mock_user_data() -> dict[str, Any]:
    """Mock user data for unit tests."""
    return {
        "id": "97108ac1-ffcb-411d-8b1e-d9183399f63b",
        "email": "unittest@example.com",
        "name": "Unit Test User",
        "is_active": True,
        "is_verified": True,
        "is_superuser": False,
    }


@pytest.fixture
def mock_team_data() -> dict[str, Any]:
    """Mock team data for unit tests."""
    return {
        "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "name": "Unit Test Team",
        "slug": "unit-test-team",
        "description": "A team for unit testing",
    }


@pytest.fixture
def mock_role_data() -> dict[str, Any]:
    """Mock role data for unit tests."""
    return {
        "id": "a47ac10b-58cc-4372-a567-0e02b2c3d479",
        "name": "Unit Test Role",
        "slug": "unit-test-role",
        "description": "A role for unit testing",
    }


@pytest.fixture
def mock_tag_data() -> dict[str, Any]:
    """Mock tag data for unit tests."""
    return {
        "id": "d47ac10b-58cc-4372-a567-0e02b2c3d479",
        "name": "Unit Test Tag",
        "slug": "unit-test-tag",
        "description": "A tag for unit testing",
    }
