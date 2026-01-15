"""Common pytest configuration shared across all test suites."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio
pytest_plugins = ["tests.fixtures.data_fixtures", "pytest_databases.docker", "pytest_databases.docker.postgres"]


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Default async backend for anyio-powered tests."""

    return "asyncio"
