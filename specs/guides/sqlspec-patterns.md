# SQLSpec Service Patterns

> **Purpose**: Guide to using SQLSpec for database operations in litestar-sqlstack
> **Audience**: Developers implementing services and database operations
> **Last Updated**: 2025-10-27
> **Status**: ✅ Current

## Overview

This guide covers the core patterns for using SQLSpec in litestar-sqlstack. SQLSpec replaces SQLAlchemy/Advanced-Alchemy for database operations with a simpler, type-safe approach using named SQL queries.

## Key Concepts

### Named SQL Queries

SQL queries are stored in separate `.sql` files in `sqlstack/db/sql/` and loaded globally:

```sql
-- sqlstack/db/sql/users.sql

-- name: get-user-by-email
SELECT id, email, name, is_active, created_at, updated_at
FROM user_account
WHERE email = :email;

-- name: list-users
SELECT id, email, name, is_active, created_at, updated_at
FROM user_account
ORDER BY created_at DESC;

-- name: create-user
INSERT INTO user_account (id, email, name, password_hash, created_at, updated_at)
VALUES (gen_random_uuid(), :email, :name, :password_hash, NOW(), NOW())
RETURNING id, email, name, is_active, created_at, updated_at;
```

### Service Base Class

All services inherit from `SQLSpecService`:

```python
# sqlstack/services/_base.py

from sqlspec.drivers.asyncpg import AsyncpgDriver
from sqlspec.pagination import OffsetPagination
from sqlspec.filters import StatementFilter

class SQLSpecService:
    """Base class for SQLSpec services."""

    def __init__(self, driver: AsyncpgDriver):
        self.driver = driver

    async def paginate(
        self,
        query: str,
        *filters: StatementFilter,
        schema_type: type[T],
    ) -> OffsetPagination[T]:
        """Execute paginated query."""
        ...

    async def get_or_404(
        self,
        query: str,
        schema_type: type[T],
        error_message: str,
        **kwargs: Any,
    ) -> T:
        """Execute query and raise 404 if not found."""
        ...
```

## Service Implementation Pattern

### Basic Service

```python
# sqlstack/services/_users.py

from sqlstack.services._base import SQLSpecService, OffsetPagination, StatementFilter
from sqlstack.config import db_manager
from sqlstack.schemas import User, UserCreate

class UserService(SQLSpecService):
    """User management service."""

    async def get_by_email(self, email: str) -> User:
        """Get user by email address."""
        return await self.get_or_404(
            db_manager.get_sql("get-user-by-email"),
            email=email,  # kwargs parameter, not dict!
            schema_type=User,
            error_message=f"User with email {email} not found"
        )

    async def list_users(self, *filters: StatementFilter) -> OffsetPagination[User]:
        """List users with pagination."""
        return await self.paginate(
            db_manager.get_sql("list-users"),
            *filters,
            schema_type=User,
        )

    async def create(self, data: UserCreate) -> User:
        """Create new user."""
        return await self.driver.select_one(
            db_manager.get_sql("create-user"),
            email=data.email,
            name=data.name,
            password_hash=hash_password(data.password),
            schema_type=User
        )
```

### Using Filters

```python
from sqlspec.filters import LimitOffsetFilter

async def list_users_paginated(
    self,
    limit: int = 10,
    offset: int = 0
) -> OffsetPagination[User]:
    """List users with explicit pagination."""
    return await self.list_users(
        LimitOffsetFilter(limit=limit, offset=offset)
    )
```

### Driver Methods

Available on `self.driver`:

- `select()` - Returns list of results
- `select_one()` - Returns single result, raises if not found
- `select_one_or_none()` - Returns single result or None
- `select_value()` - Returns single scalar value
- `execute()` - For INSERT/UPDATE/DELETE/DDL

## Parameter Binding

**CRITICAL**: Use kwargs, not dict parameters:

```python
# ✅ CORRECT
await self.driver.select_one(
    db_manager.get_sql("get-user-by-email"),
    email=user_email,  # kwargs parameter
    schema_type=User
)

# ❌ WRONG
await self.driver.select_one(
    db_manager.get_sql("get-user-by-email"),
    {"email": user_email},  # dict parameter - DO NOT USE
    schema_type=User
)
```

## Common Patterns

### Get or 404

```python
async def get_by_id(self, user_id: UUID) -> User:
    """Get user by ID or raise 404."""
    return await self.get_or_404(
        db_manager.get_sql("get-user-by-id"),
        user_id=user_id,
        schema_type=User,
        error_message=f"User {user_id} not found"
    )
```

### List with Pagination

```python
async def list_all(self, *filters: StatementFilter) -> OffsetPagination[User]:
    """List all users with pagination."""
    return await self.paginate(
        db_manager.get_sql("list-users"),
        *filters,
        schema_type=User,
    )
```

### Create/Update/Delete

```python
async def update_email(self, user_id: UUID, new_email: str) -> User:
    """Update user email."""
    return await self.driver.select_one(
        db_manager.get_sql("update-user-email"),
        user_id=user_id,
        new_email=new_email,
        schema_type=User
    )

async def delete(self, user_id: UUID) -> None:
    """Delete user."""
    await self.driver.execute(
        db_manager.get_sql("delete-user"),
        user_id=user_id
    )
```

### Transactions

```python
async def transfer_team(self, user_id: UUID, new_team_id: UUID) -> User:
    """Transfer user to new team (transactional)."""
    # SQLSpec automatically handles transactions via Litestar plugin
    # Each request gets its own transaction
    user = await self.get_by_id(user_id)

    await self.driver.execute(
        db_manager.get_sql("update-user-team"),
        user_id=user_id,
        team_id=new_team_id
    )

    return await self.get_by_id(user_id)
```

## Litestar Integration

### Dependency Injection

```python
# sqlstack/providers/__init__.py
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from sqlspec import SQLSpec
from sqlspec.adapters.asyncpg import AsyncpgConfig
from sqlspec.driver import AsyncDriverAdapterBase

from sqlstack.config import db_config, sqlspec
from sqlstack.lib.di import LitestarProvider, QueryContext, query_id_var
from sqlstack.services import UserService

if TYPE_CHECKING:
    from litestar.connection import Request


class SQLSpecProvider(Provider):
    scope = Scope.REQUEST

    @provide(scope=Scope.APP)
    def get_sqlspec_manager(self) -> SQLSpec:
        return sqlspec

    @provide(scope=Scope.APP)
    def get_database_config(self, manager: SQLSpec) -> AsyncpgConfig:
        return manager.get_config(db_config)

    @provide(scope=Scope.REQUEST)
    async def get_db_session(
        self,
        manager: SQLSpec,
        config: AsyncpgConfig,
        request: "Request[Any, Any, Any] | None" = None,
    ) -> AsyncIterator[AsyncDriverAdapterBase]:
        if request is not None:
            from sqlstack.server import plugins

            yield plugins.sqlspec.provide_async_request_session("db_session", request.app.state, request.scope)
            return

        async with manager.provide_session(config) as session:
            yield session


class CoreServiceProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def get_user_service(self, driver: AsyncDriverAdapterBase) -> UserService:
        return UserService(driver)


class ContextProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def get_query_context(self) -> QueryContext | None:
        query_id = query_id_var.get()
        if not query_id:
            return None
        return QueryContext(query_id=query_id)


def build_container() -> AsyncContainer:
    return make_async_container(
        SQLSpecProvider(),
        CoreServiceProvider(),
        ContextProvider(),
        LitestarProvider(),
    )
```

### Route Handler

```python
# sqlstack/server/routes/user.py

from sqlstack.lib.di import Inject, inject
from sqlstack.services import FilterTypes, UserService


class UserController(Controller):
    signature_types = [UserService]
    dependencies = create_filter_dependencies({...})

    @get("/users")
    @inject
    async def list_users(
        self,
        users_service: Inject[UserService],
        filters: Annotated[list[FilterTypes], Dependency(skip_validation=True)],
    ) -> OffsetPagination[s.User]:
        return await users_service.list_with_count(*filters)

    @post("/users")
    @inject
    async def create_user(
        self,
        users_service: Inject[UserService],
        data: s.UserCreate,
    ) -> s.User:
        return await users_service.create_user(data)
```

## Testing

### Fixtures

```python
# tests/conftest.py

import pytest_asyncio
from sqlstack.services import UserService

@pytest_asyncio.fixture
async def user_service(db_session) -> UserService:
    """Provide UserService for testing."""
    return UserService(db_session.driver)
```

### Test Example

```python
# tests/test_user_service.py

import pytest
from sqlstack.services import UserService
from sqlstack.schemas import UserCreate

@pytest.mark.asyncio
async def test_create_user(user_service: UserService):
    """Test creating a user."""
    # Arrange
    data = UserCreate(
        email="test@example.com",
        name="Test User",
        password="secure_password"
    )

    # Act
    user = await user_service.create(data)

    # Assert
    assert user.email == data.email
    assert user.name == data.name
    assert not hasattr(user, 'password')  # Password should not be returned
```

## Best Practices

1. **Use named SQL queries** - Store in `sqlstack/db/sql/*.sql`
2. **Use kwargs parameters** - `email=email` not `{"email": email}`
3. **Inherit from SQLSpecService** - Provides pagination, get_or_404, etc.
4. **Proper type hints** - Always specify `schema_type` parameter
5. **Error messages** - Clear, descriptive, lowercase, no periods
6. **Transactions** - Handled automatically per request
7. **Service imports** - Import from `sqlstack.services`, not `_users.py`

## Common Mistakes

❌ **Using dict parameters**:

```python
# WRONG
await self.driver.select_one(query, {"email": email})
```

❌ **Missing schema_type**:

```python
# WRONG - no type information
await self.driver.select_one(query, email=email)
```

❌ **Defensive coding**:

```python
# WRONG - hasattr/getattr anti-pattern
if hasattr(user, 'email') and user.email:
    process(user.email)
```

## Sources

- CLAUDE.md - Project standards and SQLSpec migration notes
- sqlstack/services/_base.py - Base service implementation
- sqlspec documentation - SQLSpec library patterns

## Changelog

### 2025-10-27

- Initial guide created
- Added core service patterns
- Added Litestar integration examples
- Added testing examples
- Added best practices and common mistakes
