# Testing Guide

> **Purpose**: Comprehensive guide to testing patterns in litestar-sqlstack
> **Audience**: Developers writing tests for the application
> **Last Updated**: 2025-10-28
> **Status**: ✅ Current

## Table of Contents

- [Overview](#overview)
- [Test Infrastructure](#test-infrastructure)
- [Test Organization](#test-organization)
- [Async Testing Patterns](#async-testing-patterns)
- [Database Testing](#database-testing)
- [Unit Testing Patterns](#unit-testing-patterns)
- [Integration Testing Patterns](#integration-testing-patterns)
- [Running Tests](#running-tests)
- [Coverage Reports](#coverage-reports)
- [Common Patterns](#common-patterns)

## Overview

litestar-sqlstack uses pytest with pytest-asyncio for testing. The test suite includes:

- Unit tests for lib/ and utils/ modules
- Service layer tests using SQLSpec patterns
- Integration tests for API routes
- Database tests using pytest-databases fixtures

**Test Statistics** (as of 2025-10-28):
- Total tests: 268
- Passing: 153
- Coverage: 51% overall (85-100% for lib/ and utils/)

## Test Infrastructure

### Required Dependencies

```toml
[tool.uv.dev-dependencies]
pytest = "^8.3.4"
pytest-asyncio = "^0.24.0"
pytest-databases = {extras = ["postgres"], version = "^0.10.0"}
pytest-cov = "^6.0.0"
pytest-mock = "^3.14.0"
```

### Pytest Configuration

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
addopts = [
    "--strict-markers",
    "--strict-config",
    "-ra",
]
markers = [
    "asyncio: mark test as async",
]
```

### Key Settings

- `asyncio_mode = "auto"`: Automatically detect async tests
- `asyncio_default_fixture_loop_scope = "function"`: New event loop per test
- Tests must be marked with `@pytest.mark.asyncio` for async functions

## Test Organization

```
tests/
├── conftest.py                 # Shared fixtures
├── fixtures/
│   ├── migration_fixtures.py   # Database migration fixtures
│   └── service_fixtures.py     # Service layer fixtures
├── unit/                       # Unit tests (no external dependencies)
│   ├── test_lib/              # Library module tests
│   │   ├── test_crypt.py
│   │   ├── test_types.py
│   │   ├── test_validation.py
│   │   └── test_settings.py
│   ├── test_utils/            # Utility module tests
│   │   ├── test_dto.py
│   │   ├── test_env.py
│   │   └── test_serialization.py
│   └── test_services/         # Service layer unit tests
│       ├── test_user_service.py
│       └── test_role_service.py
└── integration/               # Integration tests (with database)
    ├── test_access.py
    ├── test_routes/
    │   ├── test_user_routes.py
    │   └── test_role_routes.py
    └── test_role_management.py
```

### Unit vs Integration Tests

**Unit Tests** (`tests/unit/`):
- Test individual functions/classes in isolation
- Mock external dependencies
- Fast execution (<1s per test)
- No database required (or use in-memory)

**Integration Tests** (`tests/integration/`):
- Test multiple components together
- Use real database via postgres_service fixture
- Test full request/response cycle
- Slower execution (1-5s per test)

## Async Testing Patterns

### Basic Async Test

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test an async function."""
    result = await some_async_function()
    assert result == expected
```

### Async Fixtures

```python
import pytest

@pytest.fixture
async def async_resource():
    """Async fixture that yields a resource."""
    resource = await setup_resource()
    yield resource
    await teardown_resource(resource)

@pytest.mark.asyncio
async def test_with_async_fixture(async_resource):
    """Use an async fixture in a test."""
    result = await async_resource.do_something()
    assert result is not None
```

### Testing Async Context Managers

```python
@pytest.mark.asyncio
async def test_async_context_manager():
    """Test async context manager."""
    async with some_async_context() as ctx:
        result = await ctx.operation()
        assert result == expected
```

## Database Testing

### Using postgres_service Fixture

The `postgres_service` fixture from pytest-databases provides a temporary PostgreSQL database:

```python
import pytest
from pytest_databases.postgres import PostgresService

@pytest.mark.asyncio
async def test_database_operation(postgres_service: PostgresService):
    """Test using postgres_service fixture."""
    # Get connection details
    connection_uri = postgres_service.connection_uri

    # Run database operations
    async with get_connection(connection_uri) as conn:
        result = await conn.fetch("SELECT 1")
        assert result[0][0] == 1
```

### Migration Fixtures

Custom fixtures for running migrations:

```python
# tests/fixtures/migration_fixtures.py
import pytest
from sqlstack.db.migrations import run_migrations

@pytest.fixture
async def migrated_db(postgres_service):
    """Database with migrations applied."""
    await run_migrations(postgres_service.connection_uri)
    yield postgres_service
    # Cleanup handled by postgres_service

@pytest.mark.asyncio
async def test_with_migrations(migrated_db):
    """Test with migrated database."""
    # Database has full schema
    result = await query_user_table(migrated_db)
    assert result is not None
```

### Service Fixtures

Fixtures for testing service layer:

```python
# tests/fixtures/service_fixtures.py
import pytest
from sqlstack.services import UserService

@pytest.fixture
def mock_sqlspec(mocker):
    """Mock SQLSpec driver."""
    mock_driver = mocker.MagicMock()
    return mock_driver

@pytest.fixture
def user_service(mock_sqlspec):
    """User service with mocked driver."""
    service = UserService()
    service.driver = mock_sqlspec
    return service
```

## Unit Testing Patterns

### Testing Library Modules

Example from `tests/unit/test_lib/test_crypt.py`:

```python
import pytest
from sqlstack.lib.crypt import get_encryption_key, encrypt_string, decrypt_string

class TestEncryption:
    """Test encryption/decryption functions."""

    def test_get_encryption_key_returns_bytes(self):
        """Test that encryption key is bytes."""
        key = get_encryption_key("test-password", b"salt")
        assert isinstance(key, bytes)
        assert len(key) == 32  # 256 bits

    def test_encrypt_decrypt_round_trip(self):
        """Test encrypting and decrypting a string."""
        original = "secret-data"
        password = "password123"

        encrypted = encrypt_string(original, password)
        assert encrypted != original

        decrypted = decrypt_string(encrypted, password)
        assert decrypted == original

    def test_different_passwords_fail_decryption(self):
        """Test that wrong password fails decryption."""
        original = "secret-data"
        encrypted = encrypt_string(original, "password123")

        with pytest.raises(Exception):
            decrypt_string(encrypted, "wrong-password")
```

### Testing Utility Modules

Example from `tests/unit/test_utils/test_env.py`:

```python
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from sqlstack.utils.env import get_config_val

class TestGetConfigValString:
    """Test getting string config values."""

    def test_get_config_val_string_found(self):
        """Test retrieving existing string value."""
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            result = get_config_val("TEST_VAR", default="default")
            assert result == "test_value"

    def test_get_config_val_string_not_found(self):
        """Test default value when env var not found."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_config_val("NONEXISTENT", default="default")
            assert result == "default"

class TestGetConfigValInt:
    """Test getting integer config values."""

    def test_get_config_val_int_found(self):
        """Test retrieving integer value."""
        with patch.dict(os.environ, {"TEST_PORT": "8080"}):
            result = get_config_val("TEST_PORT", default=3000)
            assert result == 8080
            assert isinstance(result, int)
```

### Testing Validation Logic

Example from `tests/unit/test_lib/test_validation.py`:

```python
import pytest
from sqlstack.lib.validation import is_valid_email, validate_password_strength

class TestEmailValidation:
    """Test email validation."""

    @pytest.mark.parametrize("email", [
        "user@example.com",
        "test.user+tag@domain.co.uk",
        "user123@test-domain.com",
    ])
    def test_valid_emails(self, email: str):
        """Test that valid emails pass validation."""
        assert is_valid_email(email) is True

    @pytest.mark.parametrize("email", [
        "invalid.email",
        "@example.com",
        "user@",
        "user space@example.com",
    ])
    def test_invalid_emails(self, email: str):
        """Test that invalid emails fail validation."""
        assert is_valid_email(email) is False

class TestPasswordValidation:
    """Test password strength validation."""

    def test_strong_password(self):
        """Test that strong password passes."""
        result = validate_password_strength("MyP@ssw0rd123")
        assert result.is_valid is True
        assert result.score >= 80

    def test_weak_password(self):
        """Test that weak password fails."""
        result = validate_password_strength("password")
        assert result.is_valid is False
        assert result.score < 60
        assert len(result.feedback) > 0
```

## Integration Testing Patterns

### Testing API Routes

Example pattern from `tests/integration/test_routes/test_user_routes.py`:

```python
import pytest
from litestar.testing import AsyncTestClient
from sqlstack.server.app import create_app

@pytest.fixture
async def test_client(postgres_service):
    """Create test client with database."""
    app = create_app()
    async with AsyncTestClient(app=app) as client:
        yield client

class TestUserRoutes:
    """Test user API routes."""

    @pytest.mark.asyncio
    async def test_create_user(self, test_client: AsyncTestClient):
        """Test creating a user via API."""
        response = await test_client.post(
            "/api/users",
            json={
                "email": "newuser@example.com",
                "name": "New User",
                "password": "SecurePass123!"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_get_user(self, test_client: AsyncTestClient):
        """Test retrieving a user via API."""
        # Create user first
        create_response = await test_client.post(
            "/api/users",
            json={"email": "test@example.com", "password": "Pass123!"}
        )
        user_id = create_response.json()["id"]

        # Get user
        response = await test_client.get(f"/api/users/{user_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert data["email"] == "test@example.com"
```

### Testing with Authentication

```python
@pytest.fixture
async def authenticated_client(test_client: AsyncTestClient):
    """Client with authenticated user."""
    # Register user
    await test_client.post(
        "/api/auth/register",
        json={"email": "auth@example.com", "password": "Pass123!"}
    )

    # Login
    response = await test_client.post(
        "/api/auth/login",
        json={"email": "auth@example.com", "password": "Pass123!"}
    )

    token = response.json()["access_token"]
    test_client.headers["Authorization"] = f"Bearer {token}"

    return test_client

@pytest.mark.asyncio
async def test_protected_route(authenticated_client: AsyncTestClient):
    """Test accessing protected route."""
    response = await authenticated_client.get("/api/users/me")

    assert response.status_code == 200
    assert response.json()["email"] == "auth@example.com"
```

## Running Tests

### Run All Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run quietly (less output)
uv run pytest -q
```

### Run Specific Tests

```bash
# Run tests in specific directory
uv run pytest tests/unit/test_lib/

# Run specific test file
uv run pytest tests/unit/test_lib/test_crypt.py

# Run specific test class
uv run pytest tests/unit/test_lib/test_crypt.py::TestEncryption

# Run specific test method
uv run pytest tests/unit/test_lib/test_crypt.py::TestEncryption::test_encrypt_decrypt_round_trip

# Run tests matching pattern
uv run pytest -k "test_email"
```

### Run with Options

```bash
# Stop on first failure
uv run pytest -x

# Run last failed tests
uv run pytest --lf

# Run failed tests first, then others
uv run pytest --ff

# Run tests in parallel (with pytest-xdist)
uv run pytest -n auto

# Show print statements
uv run pytest -s
```

## Coverage Reports

### Generate Coverage

```bash
# Run tests with coverage
uv run pytest --cov=sqlstack

# Generate HTML coverage report
uv run pytest --cov=sqlstack --cov-report=html

# Show missing lines
uv run pytest --cov=sqlstack --cov-report=term-missing

# Coverage with specific threshold
uv run pytest --cov=sqlstack --cov-fail-under=80
```

### View Coverage

```bash
# Terminal report
uv run pytest --cov=sqlstack --cov-report=term

# HTML report (opens in browser)
uv run pytest --cov=sqlstack --cov-report=html
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux

# XML report (for CI/CD)
uv run pytest --cov=sqlstack --cov-report=xml
```

### Coverage Configuration

```toml
[tool.coverage.run]
source = ["sqlstack"]
omit = [
    "*/tests/*",
    "*/__pycache__/*",
    "*/venv/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
]
```

## Common Patterns

### Mocking with pytest-mock

```python
def test_with_mock(mocker):
    """Test using mocker fixture."""
    # Mock a function
    mock_func = mocker.patch("sqlstack.services.some_function")
    mock_func.return_value = "mocked"

    result = call_service_that_uses_some_function()

    assert result == "mocked"
    mock_func.assert_called_once()
```

### Parametrized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("test", "TEST"),
    ("hello", "HELLO"),
    ("world", "WORLD"),
])
def test_uppercase(input: str, expected: str):
    """Test uppercase conversion with multiple inputs."""
    assert input.upper() == expected
```

### Testing Exceptions

```python
def test_raises_exception():
    """Test that function raises expected exception."""
    with pytest.raises(ValueError, match="Invalid input"):
        validate_input("invalid")
```

### Using Fixtures

```python
@pytest.fixture
def sample_data():
    """Provide sample data for tests."""
    return {
        "name": "Test User",
        "email": "test@example.com",
    }

def test_with_fixture(sample_data):
    """Test using fixture."""
    assert sample_data["name"] == "Test User"
```

### Cleanup with Fixtures

```python
@pytest.fixture
def temp_file():
    """Create temporary file and clean up."""
    file_path = "/tmp/test_file.txt"

    # Setup
    with open(file_path, "w") as f:
        f.write("test data")

    yield file_path

    # Cleanup
    if os.path.exists(file_path):
        os.remove(file_path)
```

## Sources

- Local tests: tests/unit/test_lib/, tests/unit/test_utils/
- pytest documentation: https://docs.pytest.org/
- pytest-asyncio: https://pytest-asyncio.readthedocs.io/
- pytest-databases: https://pytest-databases.readthedocs.io/
- Litestar testing: https://docs.litestar.dev/latest/usage/testing.html

## Changelog

### 2025-10-28

- Initial version created
- Added async testing patterns
- Added database testing with postgres_service
- Added unit and integration test examples
- Added coverage reporting commands
- Documented test organization structure
- Added real examples from test suite (crypt, env, validation)

## Related Guides

- [SQLSpec Patterns](sqlspec-patterns.md) - Database service patterns
- [Architecture](architecture.md) - System overview (to be created)
- [Litestar Framework](litestar-framework.md) - Web framework patterns (to be created)
