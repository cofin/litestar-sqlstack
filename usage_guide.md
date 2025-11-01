# Comprehensive Guide to SQLSpec and Litestar

This guide provides a comprehensive walkthrough of building production-ready web applications using SQLSpec and Litestar, incorporating patterns from the `litestar-sqlstack` and `postgres-vertexai-demo` reference architectures.

## 1. Core Principles

- **Type Safety**: Leverage comprehensive type hints and validation.
- **Minimal Abstraction**: Stay close to SQL for performance and flexibility.
- **Performance**: Utilize `msgspec` for high-speed data serialization.
- **Flexibility**: Combine raw SQL files and dynamic query builders.
- **Modern DI**: Use `dishka` for clean, testable dependency injection.

## 2. Project Structure

A well-organized project structure is key to maintainability.

```
project/
├── config.py              # Central configuration for Litestar and SQLSpec
├── lib/
│   ├── di.py              # Dependency injection setup (Dishka)
│   └── settings.py      # Environment-based settings
├── db/
│   ├── migrations/        # SQL-based schema migrations
│   └── sql/               # Named SQL query files
├── schemas/
│   └── ...                # msgspec data transfer objects (DTOs)
├── services/
│   ├── _base.py           # Base service class for business logic
│   └── ...                # Concrete service implementations
└── server/
    ├── core.py            # Litestar application core plugin
    ├── deps.py            # Legacy dependency providers (or DI providers)
    └── routes/
        └── ...            # API endpoint controllers
```

## 3. Configuration

### 3.1. SQLSpec Manager (`config.py`)

The `SQLSpec` object is the central manager for all database configurations.

```python
# /sqlstack/config.py
from sqlspec import SQLSpec
from sqlspec.adapters.asyncpg import AsyncpgConfig
from sqlspec.adapters.duckdb import DuckDBConfig
from sqlstack.lib.settings import get_settings, BASE_DIR

settings = get_settings()

# 1. Initialize the SQLSpec manager
sqlspec = SQLSpec()

# 2. Add a primary database configuration (e.g., PostgreSQL)
db_config = sqlspec.add_config(
    AsyncpgConfig(
        pool_config={
            "dsn": settings.db.URL,
            "min_size": settings.db.POOL_MIN_SIZE,
            "max_size": settings.db.POOL_MAX_SIZE,
        },
        migration_config={
            "version_table_name": settings.db.MIGRATION_DDL_VERSION_TABLE,
            "script_location": settings.db.MIGRATION_PATH,
        },
        extension_config={
            "litestar": {
                "commit_mode": "autocommit",
                "session_key": "db_session", # Key for DI
            }
        },
    )
)

# 3. Add another database configuration (e.g., DuckDB for analytics)
etl_config = sqlspec.add_config(
    DuckDBConfig(
        extension_config={
            "litestar": {
                "session_key": "etl_session", # Use a distinct key
            }
        }
    )
)

# 4. Load all named SQL queries from the specified directory
sqlspec.load_sql_files(BASE_DIR / "sqlstack" / "db" / "sql")
```

### 3.2. Litestar Plugin (`server/plugins.py`)

Integrate SQLSpec into Litestar using the `SQLSpecPlugin`.

```python
# /sqlstack/server/plugins.py
from sqlspec.extensions.litestar import SQLSpecPlugin
from sqlstack import config

# The plugin makes the SQLSpec manager available to the Litestar app
sqlspec = SQLSpecPlugin(sqlspec=config.sqlspec)
```

This plugin automatically provides dependencies like `db_session` (the driver for the default config) to your route handlers.

## 4. Dependency Injection with Dishka

For more complex applications, `dishka` provides a robust and explicit way to manage dependencies like services and database drivers.

### 4.1. Setup (`lib/di.py`)

Create a clean interface for `dishka` to avoid tight coupling with the framework.

```python
# /postgres-vertexai-demo/app/lib/di.py
from dishka import AsyncContainer, Provider, Scope, provide
from dishka.integrations.litestar import FromDishka as Inject, inject, setup_dishka

# Re-export for clean, consistent usage across the app
__all__ = (
    "AsyncContainer",
    "Inject",
    "Provider",
    "Scope",
    "inject",
    "provide",
    "setup_dishka",
)
```

### 4.2. Provider Configuration

Define providers for your services and the database driver.

```python
# /postgres-vertexai-demo/app/server/providers.py (example)
from dishka import Provider, Scope, provide
from sqlspec import AsyncDriverAdapterBase
from app import services
from app.config import db_manager, db

# Create a provider instance
main_provider = Provider(scope=Scope.REQUEST)

# Provide the database driver
@provide(scope=Scope.REQUEST)
async def provide_db_driver() -> AsyncIterator[AsyncDriverAdapterBase]:
    async with db_manager.provide_session(db) as driver:
        yield driver

# Provide services that depend on the driver
main_provider.provide(services.ProductService)
main_provider.provide(services.VectorSearchService)
# ... other services
```

### 4.3. Application Integration (`server/core.py`)

Set up the `dishka` container in your Litestar `on_app_init` hook.

```python
# /postgres-vertexai-demo/app/server/core.py
from litestar.config.app import AppConfig
from app.lib.di import setup_dishka
from app.server.providers import main_provider # Your provider from above

class ApplicationCore(InitPluginProtocol):
    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        # ... other configurations
        app_config.listeners.append(setup_dishka([main_provider]))
        # ...
        return app_config
```

### 4.4. Injecting Dependencies

Use the `@inject` decorator and `Inject` type hint in your controllers.

```python
# /postgres-vertexai-demo/app/server/controllers.py (example)
from app.lib.di import Inject, inject
from app.services import ProductService

class MyController(Controller):
    @get("/")
    @inject
    async def my_handler(self, product_service: Inject[ProductService]) -> list[Product]:
        return await product_service.list()
```

## 5. Service Layer

The service layer contains your application's business logic. A base service class provides common functionality.

### 5.1. Base Service (`services/_base.py`)

The `SQLSpecService` provides essential methods for database interaction.

```python
# /sqlstack/services/_base.py
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, TypeVar

from sqlspec.driver import AsyncDriverAdapterBase
from sqlspec.core.filters import LimitOffsetFilter, OffsetPagination, StatementFilter
from sqlspec.typing import SchemaT

if TYPE_CHECKING:
    from sqlspec import QueryBuilder, Statement

class SQLSpecService:
    """Base service class for SQLSpec operations."""

    def __init__(self, driver: AsyncDriverAdapterBase) -> None:
        self.driver = driver

    async def paginate(
        self,
        statement: Statement | QueryBuilder,
        /,
        *filters: StatementFilter,
        schema_type: type[SchemaT],
        **kwargs: Any,
    ) -> OffsetPagination[SchemaT]:
        """Paginate data using a statement and filters."""
        results, total = await self.driver.select_with_total(
            statement, *filters, schema_type=schema_type, **kwargs
        )
        limit_offset = self.driver.find_filter(LimitOffsetFilter, filters)
        return OffsetPagination[SchemaT](
            items=results,
            limit=limit_offset.limit if limit_offset else 10,
            offset=limit_offset.offset if limit_offset else 0,
            total=total,
        )

    async def get_or_404(
        self,
        statement: Statement | QueryBuilder,
        /,
        schema_type: type[SchemaT],
        error_message: str | None = None,
        **kwargs: Any,
    ) -> SchemaT:
        """Fetch a single record or raise a 404-style error."""
        result = await self.driver.select_one_or_none(
            statement, schema_type=schema_type, **kwargs
        )
        if result is None:
            # In a real app, this would raise a Litestar HTTPException
            raise ValueError(error_message or "Record not found")
        return result

    @asynccontextmanager
    async def begin_transaction(self) -> AsyncIterator[None]:
        """Context manager for manual database transactions."""
        await self.driver.begin()
        try:
            yield
        except Exception:
            await self.driver.rollback()
            raise
        else:
            await self.driver.commit()
```

### 5.2. Concrete Service (`services/_users.py`)

Services inherit from `SQLSpecService` and use the injected driver to execute queries.

```python
# /sqlstack/services/_users.py
from sqlstack import schemas as s
from sqlstack.config import sqlspec as db_manager
from sqlstack.services._base import OffsetPagination, SQLSpecService, StatementFilter

class UserService(SQLSpecService):
    async def get_user(self, user_id: UUID) -> s.User:
        """Get a single user by ID."""
        return await self.get_or_404(
            db_manager.get_sql("get-user-account-details"),
            schema_type=s.User,
            user_id=user_id,
            error_message=f"User {user_id} not found",
        )

    async def list_with_count(self, *filters: StatementFilter) -> OffsetPagination[s.User]:
        """List users with pagination and filtering."""
        return await self.paginate(
            db_manager.get_sql("list-users"),
            *filters,
            schema_type=s.User,
        )
```

## 6. Database Queries

### 6.1. Named SQL Queries (`db/sql/`)

Store reusable, complex, or performance-critical queries in `.sql` files. This keeps SQL out of your Python code and makes it easier for DBAs to review.

```sql
-- /sqlstack/db/sql/users.sql

-- name: get-user-account-details
-- Get a user with their associated roles and teams aggregated into JSON
SELECT
    u.id, u.email, u.name,
    (u.hashed_password IS NOT NULL) as has_password,
    -- ... other user fields
    COALESCE(
        jsonb_agg(DISTINCT jsonb_build_object(...)) FILTER (...), '[]'::jsonb
    ) as teams,
    COALESCE(
        jsonb_agg(DISTINCT jsonb_build_object(...)) FILTER (...), '[]'::jsonb
    ) as roles
FROM user_account u
LEFT JOIN team_member tm ON u.id = tm.user_id
-- ... other joins
WHERE u.id = :user_id
GROUP BY u.id;

-- name: list-users
SELECT id, email, name, ...
FROM user_account
ORDER BY created_at DESC
LIMIT :limit OFFSET :offset;
```

### 6.2. Query Builder

Use the query builder for simple or dynamic queries constructed at runtime.

```python
from sqlspec import sql

# Simple SELECT
query = sql.select("id", "name").from_("user_account").where_eq("is_active", True)

# Dynamic UPDATE
update_data = {"name": "New Name", "updated_at": sql.raw("NOW()")}
query = sql.update("user_account").set(**update_data).where_eq("id", user_id)
```

## 7. Filters and Pagination

SQLSpec provides a powerful filtering system that integrates with Litestar.

### 7.1. Automatic Filter Dependencies

Use the `create_filter_dependencies` provider to automatically generate dependencies for common filters like pagination, sorting, and searching.

```python
# /sqlstack/server/routes/user.py
from sqlspec.extensions.litestar.providers import create_filter_dependencies

class UserController(Controller):
    path = "/api/users"
    dependencies = {
        "users_service": Provide(deps.provide_users_service),
    } | create_filter_dependencies({
            "id_filter": UUID,
            "search": "name,email", # Creates a SearchFilter for these fields
            "pagination_type": "limit_offset",
            "created_at": True, # Creates BeforeAfterFilter for created_at
            "sort_field": "name", # Default for OrderByFilter
        })

    @get()
    async def list_users(
        self,
        users_service: UserService,
        filters: Annotated[list[FilterTypes], Dependency(skip_validation=True)]
    ) -> OffsetPagination[s.User]:
        # The 'filters' dependency will contain a list of populated filter
        # instances based on the query parameters provided by the client.
        return await users_service.list_with_count(*filters)
```

A client can then make a request like:
`/api/users?limit=50&offset=100&search=john&sort_order=desc`

The `filters` argument will automatically contain `LimitOffsetFilter(limit=50, offset=100)`, `SearchFilter(search_columns=['name', 'email'], value='john')`, and `OrderByFilter(field='name', order='desc')`.

### 7.2. How It Works in the Service

The `SQLSpecService` base class and `driver` can automatically find and apply these filters. The `paginate` method handles `LimitOffsetFilter` and `OrderByFilter` automatically. Other filters are applied by the driver's `select_with_total` method.

## 8. Transaction Management

Ensure data integrity by using transactions for operations that involve multiple database writes.

### 8.1. Autocommit (Default)

When `commit_mode` is `"autocommit"` in the Litestar extension config, SQLSpec automatically commits the transaction if the request is successful (2xx status code) and rolls back on any exception. This is suitable for most simple CRUD operations.

### 8.2. Manual Transactions

For complex operations spanning multiple service methods or requiring fine-grained control, use the `begin_transaction` context manager.

```python
# In a service method
async def create_user_and_team(self, user_data: s.UserCreate, team_name: str) -> s.User:
    async with self.begin_transaction():
        # All operations within this block are part of a single transaction
        user = await self.create_user(user_data)
        team_data = s.TeamCreate(name=team_name, owner_id=user.id)
        await self.team_service.create(team_data) # Assuming team_service is available
        return user
    # The transaction is automatically committed on exit, or rolled back on exception.
```
