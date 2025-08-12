"""Integration test configuration."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
async def setup_integration_environment() -> None:
    """Setup environment for integration tests."""
    # Any integration-specific setup can go here


@pytest.fixture
async def clean_database(db_connection) -> None:
    """Clean database between integration tests."""
    # Clean up test data
    tables = [
        "password_reset_token",
        "email_verification_token",
        "team",
        "tag",
        "role",
        "user_account",
    ]

    for table in tables:
        await db_connection.execute(f"DELETE FROM {table}")

    # Reset sequences if needed
    for table in tables:
        await db_connection.execute(f"ALTER SEQUENCE IF EXISTS {table}_id_seq RESTART WITH 1")
