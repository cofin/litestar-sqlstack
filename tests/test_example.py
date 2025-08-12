"""Example test to verify test setup works."""

import pytest

from sqlstack import schemas as s


@pytest.mark.unit
def test_example_schema() -> None:
    """Example test to verify schemas work."""
    user_create = s.UserCreate(
        email="test@example.com",
        password="TestPassword123!",
        name="Test User"
    )

    assert user_create.email == "test@example.com"
    assert user_create.name == "Test User"
    assert user_create.is_active is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_example_async() -> None:
    """Example async test."""
    # This would use actual services with database
    assert True  # Placeholder
