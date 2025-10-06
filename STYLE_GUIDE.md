# Comprehensive SQLSpec & Litestar Web Application Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Configuration](#core-configuration)
4. [Database Layer with SQLSpec](#database-layer-with-sqlspec)
5. [Service Layer Architecture](#service-layer-architecture)
6. [Controllers and Routes](#controllers-and-routes)
7. [Authentication and Security](#authentication-and-security)
8. [Filters and Pagination](#filters-and-pagination)
9. [Dependency Injection](#dependency-injection)
10. [Schema and Data Transfer Objects](#schema-and-data-transfer-objects)
11. [SQL Files vs Query Builders](#sql-files-vs-query-builders)
12. [Transaction Management](#transaction-management)
13. [Testing Strategies](#testing-strategies)
14. [Best Practices and Patterns](#best-practices-and-patterns)
15. [Complete Example: Building a Feature](#complete-example-building-a-feature)

## Introduction

SQLSpec is a modern SQL toolkit that provides a powerful abstraction layer over database operations while maintaining the flexibility and performance of raw SQL. When combined with Litestar, a high-performance ASGI framework, you get a robust foundation for building scalable web applications.

This guide provides a comprehensive walkthrough of building production-ready web applications using SQLSpec and Litestar, covering everything from initial setup to advanced patterns.

## Project Structure

The recommended project structure separates concerns into distinct layers:

```
project/
├── cli/                    # CLI commands
│   ├── __init__.py
│   └── commands.py         # Custom management commands
├── config.py              # Central configuration
├── db/                    # Database layer
│   ├── migrations/        # Schema migrations
│   │   ├── 0001_initial.sql
│   │   └── README.md
│   ├── fixtures/          # Test/seed data
│   │   └── initial_data.json
│   └── sql/              # Named SQL queries
│       ├── users.sql
│       ├── teams.sql
│       └── roles.sql
├── lib/                   # Core utilities
│   ├── crypt.py          # Password hashing
│   ├── email.py          # Email utilities
│   ├── exceptions.py     # Custom exceptions
│   ├── log.py           # Logging configuration
│   ├── settings.py      # Settings management
│   └── types.py         # Custom type definitions
├── schemas/              # Pydantic/msgspec schemas
│   ├── __init__.py
│   ├── base.py          # Base schema classes
│   ├── _accounts.py     # User account schemas
│   ├── _teams.py        # Team schemas
│   └── _roles.py        # Role schemas
├── server/               # Litestar application
│   ├── asgi.py         # ASGI application entry
│   ├── core.py          # Core plugin configuration
│   ├── deps.py          # Dependency providers
│   ├── security.py      # Security configuration
│   ├── routes/          # API endpoints
│   │   ├── __init__.py
│   │   ├── access.py    # Auth endpoints
│   │   ├── user.py      # User endpoints
│   │   └── team.py      # Team endpoints
│   ├── events/          # Event handlers
│   │   └── user.py      # User events
│   └── plugins.py       # Plugin configurations
├── services/             # Business logic layer
│   ├── __init__.py
│   ├── _base.py         # Base service class
│   ├── _users.py        # User service
│   ├── _teams.py        # Team service
│   └── _roles.py        # Role service
└── utils/                # Shared utilities
    ├── dto.py           # DTO utilities
    ├── env.py           # Environment helpers
    └── serialization.py # Serialization utilities
```

## Core Configuration

### Main Configuration File (config.py)

The configuration file sets up all core components including database connections, logging, CORS, and the SQLSpec plugin:

```python
import logging
from pathlib import Path
from typing import cast

import structlog
from litestar.config.compression import CompressionConfig
from litestar.config.cors import CORSConfig
from litestar.config.csrf import CSRFConfig
from litestar.plugins.structlog import StructlogConfig
from sqlspec.adapters.asyncpg import AsyncpgConfig
from sqlspec.adapters.duckdb import DuckDBConfig
from sqlspec.extensions.litestar import DatabaseConfig, SQLSpec

from lib.settings import get_settings
from utils.env import BASE_DIR

# Load settings from environment
settings = get_settings()

# Define role constants
DEFAULT_ACCESS_ROLE = "User"
SUPERUSER_ACCESS_ROLE = "Superuser"

# Configure compression
compression = CompressionConfig(backend="gzip")

# Configure CSRF protection
csrf = CSRFConfig(
    secret=settings.app.SECRET_KEY,
    cookie_secure=settings.app.CSRF_COOKIE_SECURE,
    cookie_name=settings.app.CSRF_COOKIE_NAME,
    header_name=settings.app.CSRF_HEADER_NAME,
)

# Configure CORS
cors = CORSConfig(
    allow_origins=cast("list[str]", settings.app.ALLOWED_CORS_ORIGINS)
)

# Configure primary database (PostgreSQL)
db = AsyncpgConfig(
    pool_config={
        "dsn": settings.db.URL,
        "min_size": settings.db.POOL_MIN_SIZE,
        "max_size": settings.db.POOL_MAX_SIZE,
        "timeout": settings.db.POOL_TIMEOUT,
        "command_timeout": settings.db.POOL_RECYCLE,
    },
    migration_config={
        "version_table_name": settings.db.MIGRATION_DDL_VERSION_TABLE,
        "script_location": settings.db.MIGRATION_PATH,
        "project_root": BASE_DIR,
    },
)

# Configure ETL database (DuckDB for analytics)
etl_db = DuckDBConfig()

# Initialize SQLSpec manager
db_manager = SQLSpec(
    config=[
        DatabaseConfig(
            commit_mode="autocommit",
            config=db
        ),
        DatabaseConfig(
            config=etl_db,
            connection_key="etl_connection",
            pool_key="etl_pool",
            session_key="etl_session"
        ),
    ],
)

# Load SQL files from the db/sql directory
db_manager.load_sql_files(BASE_DIR / "db" / "sql")

# Configure structured logging
log = StructlogConfig(
    enable_middleware_logging=False,
    structlog_logging_config=StructLoggingConfig(
        log_exceptions="always",
        processors=log_conf.structlog_processors(as_json=True),
        logger_factory=default_logger_factory(as_json=True),
    ),
)
```

### Settings Management (lib/settings.py)

Use Pydantic Settings for environment-based configuration:

```python
from functools import lru_cache
from typing import Any

from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        case_sensitive=False,
    )

    NAME: str = "My Application"
    DEBUG: bool = False
    SECRET_KEY: SecretStr
    ALLOWED_CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    JWT_ENCRYPTION_ALGORITHM: str = "HS256"

    CSRF_COOKIE_NAME: str = "csrftoken"
    CSRF_COOKIE_SECURE: bool = True
    CSRF_HEADER_NAME: str = "x-csrftoken"


class DatabaseSettings(BaseSettings):
    """Database settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DB_",
        case_sensitive=False,
    )

    URL: PostgresDsn
    POOL_MIN_SIZE: int = 10
    POOL_MAX_SIZE: int = 50
    POOL_TIMEOUT: float = 5.0
    POOL_RECYCLE: float = 300.0

    MIGRATION_DDL_VERSION_TABLE: str = "_db_migrations"
    MIGRATION_PATH: str = "db/migrations"


class Settings(BaseSettings):
    """Combined settings."""

    app: AppSettings = Field(default_factory=AppSettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    log: LogSettings = Field(default_factory=LogSettings)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

## Database Layer with SQLSpec

### Named SQL Queries

Store SQL queries in separate files under `db/sql/`. Each query has a name comment that SQLSpec uses to reference it:

**db/sql/users.sql:**

```sql
-- name: create-user
INSERT INTO user_account (
    id, email, name, hashed_password,
    avatar_url, is_active, is_verified, created_at
)
VALUES (
    gen_random_uuid(), :email, :name, :hashed_password,
    :avatar_url, COALESCE(:is_active, true),
    COALESCE(:is_verified, false), NOW()
)
RETURNING id, email, name, is_active, is_verified, created_at, updated_at;

-- name: get-user-by-id
SELECT
    u.id, u.email, u.name, u.avatar_url,
    u.is_active, u.is_verified, u.created_at, u.updated_at,
    CASE WHEN u.hashed_password IS NOT NULL THEN true ELSE false END as has_password,
    COALESCE(
        json_agg(
            DISTINCT jsonb_build_object(
                'role_id', r.id,
                'role_name', r.name,
                'role_slug', r.slug,
                'assigned_at', ur.assigned_at
            )
        ) FILTER (WHERE r.id IS NOT NULL),
        '[]'::json
    ) as roles,
    COALESCE(
        json_agg(
            DISTINCT jsonb_build_object(
                'team_id', tm.team_id,
                'team_name', t.name,
                'role', tm.role,
                'is_owner', tm.is_owner
            )
        ) FILTER (WHERE tm.team_id IS NOT NULL),
        '[]'::json
    ) as teams
FROM user_account u
LEFT JOIN user_role ur ON u.id = ur.user_id
LEFT JOIN role r ON ur.role_id = r.id
LEFT JOIN team_member tm ON u.id = tm.user_id
LEFT JOIN team t ON tm.team_id = t.id
WHERE u.id = :user_id
GROUP BY u.id;

-- name: list-users
SELECT
    u.id, u.email, u.name, u.avatar_url,
    u.is_active, u.is_verified,
    u.created_at, u.updated_at
FROM user_account u
WHERE 1=1
    AND (:search IS NULL OR u.name ILIKE '%' || :search || '%' OR u.email ILIKE '%' || :search || '%')
    AND (:is_active IS NULL OR u.is_active = :is_active)
    AND (:is_verified IS NULL OR u.is_verified = :is_verified)
ORDER BY
    CASE WHEN :sort_field = 'name' AND :sort_order = 'asc' THEN u.name END ASC,
    CASE WHEN :sort_field = 'name' AND :sort_order = 'desc' THEN u.name END DESC,
    CASE WHEN :sort_field = 'created_at' AND :sort_order = 'asc' THEN u.created_at END ASC,
    CASE WHEN :sort_field = 'created_at' AND :sort_order = 'desc' THEN u.created_at END DESC,
    u.created_at DESC
LIMIT :limit OFFSET :offset;

-- name: count-users
SELECT COUNT(*) as total
FROM user_account u
WHERE 1=1
    AND (:search IS NULL OR u.name ILIKE '%' || :search || '%' OR u.email ILIKE '%' || :search || '%')
    AND (:is_active IS NULL OR u.is_active = :is_active)
    AND (:is_verified IS NULL OR u.is_verified = :is_verified);

-- name: update-user-password
UPDATE user_account
SET
    hashed_password = :hashed_password,
    updated_at = NOW()
WHERE id = :user_id
RETURNING id, email, name, updated_at;

-- name: user-exists-by-email
SELECT EXISTS(
    SELECT 1 FROM user_account WHERE email = :email
) as exists;
```

### Query Builder Usage

SQLSpec provides a fluent SQL builder for dynamic queries:

```python
from sqlspec import sql

# Simple SELECT
query = sql.select("id", "name", "email").from_("user_account").where_eq("is_active", True)

# Complex JOIN with conditions
query = (
    sql.select("u.id", "u.name", "t.name as team_name")
    .from_("user_account", "u")
    .left_join("team_member", "tm", "u.id = tm.user_id")
    .left_join("team", "t", "tm.team_id = t.id")
    .where("u.is_active = :is_active")
    .where("t.id = :team_id")
    .order_by("u.name ASC")
)

# INSERT with returning
query = (
    sql.insert("user_account")
    .values(
        email=user_data["email"],
        name=user_data["name"],
        hashed_password=hashed_password
    )
    .returning("id", "email", "name", "created_at")
)

# UPDATE with conditions
query = (
    sql.update("user_account")
    .set(
        name=new_name,
        updated_at=sql.raw("NOW()")
    )
    .where_eq("id", user_id)
    .where("is_active = true")
)

# DELETE
query = sql.delete("user_account").where_eq("id", user_id)

# Using raw SQL when needed
query = sql.raw("""
    WITH user_stats AS (
        SELECT user_id, COUNT(*) as post_count
        FROM posts
        GROUP BY user_id
    )
    SELECT u.*, us.post_count
    FROM user_account u
    LEFT JOIN user_stats us ON u.id = us.user_id
    WHERE u.is_active = :is_active
""")
```

## Service Layer Architecture

### Base Service Class

The base service provides common database operations:

```python
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, TypeVar, cast

from sqlspec.core.filters import (
    LimitOffsetFilter,
    OffsetPagination,
    StatementFilter,
)
from sqlspec.driver import AsyncDriverAdapterBase
from sqlspec.typing import ModelDTOT, StatementParameters

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Sequence
    from sqlspec import QueryBuilder, Statement, StatementConfig

T = TypeVar("T")


class SQLSpecService:
    """Base service class for SQLSpec operations."""

    def __init__(self, driver: AsyncDriverAdapterBase) -> None:
        """Initialize the service with a database driver."""
        self.driver = driver

    async def paginate(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters | StatementFilter,
        schema_type: type[ModelDTOT],
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> OffsetPagination[ModelDTOT]:
        """Execute paginated query with total count.

        Returns OffsetPagination object with items, limit, offset, and total.
        """
        results, total = await self.driver.select_with_total(
            statement,
            *parameters,
            schema_type=schema_type,
            statement_config=statement_config,
            **kwargs,
        )
        limit_offset = self.find_filter(LimitOffsetFilter, parameters)
        offset = limit_offset.offset if limit_offset else 0
        limit = limit_offset.limit if limit_offset else 10
        return OffsetPagination[ModelDTOT](
            items=results,
            limit=limit,
            offset=offset,
            total=total
        )

    async def get_or_404(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        schema_type: type[ModelDTOT],
        error_message: str | None = None,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> ModelDTOT:
        """Get single record or raise ValueError if not found."""
        result = await self.driver.select_one_or_none(
            statement,
            *parameters,
            schema_type=schema_type,
            statement_config=statement_config,
            **kwargs,
        )
        if result is None:
            raise ValueError(error_message or "Record not found")
        return result

    async def exists(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        statement_config: StatementConfig | None = None,
        **kwargs: Any,
    ) -> bool:
        """Check if a record exists."""
        result = await self.driver.select_one_or_none(
            statement,
            *parameters,
            statement_config=statement_config,
            **kwargs,
        )
        return result is not None

    @staticmethod
    def find_filter(
        filter_type: type[FilterTypeT],
        filters: Sequence[StatementFilter | StatementParameters],
    ) -> FilterTypeT | None:
        """Find specific filter type from filter list."""
        return next(
            (
                cast("FilterTypeT | None", filter_)
                for filter_ in filters
                if isinstance(filter_, filter_type)
            ),
            None,
        )

    @asynccontextmanager
    async def begin_transaction(self) -> AsyncGenerator[None, None]:
        """Transaction context manager for atomic operations."""
        try:
            await self.driver.begin()
            yield
            await self.driver.commit()
        except Exception:
            await self.driver.rollback()
            raise
```

### Implementing a Service

Services inherit from the base class and implement business logic:

```python
from typing import TYPE_CHECKING
from uuid import UUID

from litestar.exceptions import PermissionDeniedException
from sqlspec import sql
from sqlspec.utils.text import slugify
from sqlspec.utils.type_guards import schema_dump

from schemas import User, UserCreate, UserUpdate, AccountRegister
from config import db_manager
from lib.crypt import get_password_hash, verify_password
from services._base import OffsetPagination, SQLSpecService, StatementFilter

if TYPE_CHECKING:
    from sqlspec.driver import AsyncDriverAdapterBase


class UserService(SQLSpecService):
    """Handles database operations for users."""

    async def create_user(
        self,
        data: UserCreate | AccountRegister
    ) -> User:
        """Create a new user account with role and team setup."""
        # Convert schema to dict and handle password
        user_data = schema_dump(data, exclude_unset=True)
        if password := user_data.pop("password", None):
            user_data["hashed_password"] = await get_password_hash(password)

        # Extract optional team name
        initial_team = user_data.pop("initial_team_name", None)

        # Create user using named query
        result = await self.driver.select_one(
            db_manager.get_sql("create-user"),
            schema_type=User,
            **user_data
        )

        # Assign default role using query builder
        if default_role := await self._get_default_role():
            await self.driver.execute(
                sql.insert("user_role").values(
                    user_id=result.id,
                    role_id=default_role.id
                )
            )

        # Create initial team if requested
        if initial_team:
            team_slug = await self._get_unique_slug(initial_team)
            team_id = await self.driver.select_value(
                sql.insert("team")
                .values(name=initial_team, slug=team_slug)
                .returning("id")
            )
            await self.driver.execute(
                sql.insert("team_member").values(
                    user_id=result.id,
                    team_id=team_id,
                    role="owner",
                    is_owner=True
                )
            )

        # Return full user with relationships
        return await self.get_user(result.id)

    async def update_user(
        self,
        user_id: UUID,
        data: UserUpdate
    ) -> User:
        """Update user account details."""
        # Use query builder for simple updates
        await self.driver.execute(
            sql.update("user_account")
            .set(**schema_dump(data, exclude_unset=True))
            .where_eq("id", user_id)
        )
        return await self.get_user(user_id)

    async def delete_user(self, user_id: UUID) -> None:
        """Soft delete a user account."""
        # Use query builder for status updates
        await self.driver.execute(
            sql.update("user_account")
            .set(is_active=False, deleted_at=sql.raw("NOW()"))
            .where_eq("id", user_id)
        )

    async def get_user(self, user_id: UUID) -> User:
        """Get user with all relationships."""
        # Use named query for complex joins
        return await self.get_or_404(
            db_manager.get_sql("get-user-by-id"),
            user_id=user_id,
            schema_type=User,
            error_message=f"User {user_id} not found"
        )

    async def list_users(
        self,
        *filters: StatementFilter
    ) -> OffsetPagination[User]:
        """List users with pagination and filtering."""
        # Use paginate helper with named queries
        return await self.paginate(
            db_manager.get_sql("list-users"),
            *filters,
            schema_type=User
        )

    async def authenticate(
        self,
        email: str,
        password: str
    ) -> User:
        """Authenticate user by email and password."""
        # Get user with password hash
        auth_data = await self.driver.select_one_or_none(
            sql.select("id", "email", "hashed_password", "is_active")
            .from_("user_account")
            .where_eq("email", email)
        )

        if not auth_data:
            raise PermissionDeniedException("Invalid credentials")

        # Verify password
        if not await verify_password(password, auth_data["hashed_password"]):
            raise PermissionDeniedException("Invalid credentials")

        # Check if account is active
        if not auth_data["is_active"]:
            raise PermissionDeniedException("Account is inactive")

        # Update last login
        await self.driver.execute(
            sql.update("user_account")
            .set(last_login=sql.raw("NOW()"))
            .where_eq("id", auth_data["id"])
        )

        return await self.get_user(auth_data["id"])

    async def update_password(
        self,
        user_id: UUID,
        current_password: str,
        new_password: str
    ) -> User:
        """Update user password after verification."""
        # Get current password hash
        current = await self.driver.select_one(
            sql.select("hashed_password")
            .from_("user_account")
            .where_eq("id", user_id)
        )

        # Verify current password
        if not await verify_password(current_password, current["hashed_password"]):
            raise ValueError("Current password is incorrect")

        # Update with new password
        new_hash = await get_password_hash(new_password)
        await self.driver.execute(
            db_manager.get_sql("update-user-password"),
            user_id=user_id,
            hashed_password=new_hash
        )

        return await self.get_user(user_id)

    async def bulk_deactivate(
        self,
        user_ids: list[UUID]
    ) -> int:
        """Deactivate multiple users at once."""
        # Use query builder for bulk operations
        result = await self.driver.execute(
            sql.update("user_account")
            .set(is_active=False, updated_at=sql.raw("NOW()"))
            .where(sql.column("id").in_(user_ids))
        )
        return result.rowcount

    async def search_users(
        self,
        query: str,
        limit: int = 10
    ) -> list[User]:
        """Search users by name or email."""
        # Use named query for search
        return await self.driver.select(
            db_manager.get_sql("search-users"),
            query=query,
            limit=limit,
            schema_type=User
        )

    async def _get_default_role(self) -> Role | None:
        """Get the default user role."""
        return await self.driver.select_one_or_none(
            sql.select("id", "name", "slug")
            .from_("role")
            .where_eq("slug", "user")
        )

    async def _get_unique_slug(self, name: str) -> str:
        """Generate a unique slug for the given name."""
        base_slug = slugify(name)
        slug = base_slug
        counter = 1

        while await self.exists(
            sql.select("id").from_("team").where_eq("slug", slug)
        ):
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug
```

### When to Use SQL Files vs Query Builders

**Use SQL Files When:**

- Complex queries with multiple JOINs, CTEs, or window functions
- Queries that are stable and rarely change
- Performance-critical queries that need optimization
- Queries with complex business logic
- Reports and analytics queries
- Queries that benefit from SQL-specific features

**Example scenarios for SQL files:**

```sql
-- name: get-user-activity-report
WITH activity_summary AS (
    SELECT
        u.id as user_id,
        COUNT(DISTINCT l.id) as login_count,
        COUNT(DISTINCT p.id) as post_count,
        MAX(l.created_at) as last_login
    FROM user_account u
    LEFT JOIN login_history l ON u.id = l.user_id
    LEFT JOIN posts p ON u.id = p.author_id
    WHERE l.created_at >= NOW() - INTERVAL '30 days'
    GROUP BY u.id
),
team_summary AS (
    SELECT
        tm.user_id,
        array_agg(t.name) as team_names,
        COUNT(*) as team_count
    FROM team_member tm
    JOIN team t ON tm.team_id = t.id
    GROUP BY tm.user_id
)
SELECT
    u.*,
    as.login_count,
    as.post_count,
    as.last_login,
    ts.team_names,
    ts.team_count
FROM user_account u
LEFT JOIN activity_summary as ON u.id = as.user_id
LEFT JOIN team_summary ts ON u.id = ts.user_id
WHERE u.is_active = true
ORDER BY as.login_count DESC;
```

**Use Query Builder When:**

- Simple CRUD operations
- Dynamic queries with conditional clauses
- Updates based on user input
- Quick prototyping
- Queries that change based on runtime conditions

**Example scenarios for query builder:**

```python
# Dynamic filtering
query = sql.select("*").from_("products")

if category_id:
    query = query.where_eq("category_id", category_id)

if min_price:
    query = query.where("price >= :min_price", min_price=min_price)

if search_term:
    query = query.where("name ILIKE :search", search=f"%{search_term}%")

# Dynamic updates
update = sql.update("user_account")
if new_name:
    update = update.set(name=new_name)
if new_email:
    update = update.set(email=new_email)
update = update.where_eq("id", user_id)

# Bulk operations
await self.driver.execute(
    sql.delete("notifications")
    .where("user_id = :user_id")
    .where("created_at < :cutoff_date"),
    user_id=user_id,
    cutoff_date=cutoff_date
)
```

## Controllers and Routes

### Controller Structure

Controllers handle HTTP requests and delegate to services:

```python
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from litestar import Controller, delete, get, patch, post
from litestar.di import Provide
from litestar.params import Dependency, Parameter
from sqlspec.extensions.litestar.providers import create_filter_dependencies

from server import deps, security
from services import FilterTypes

if TYPE_CHECKING:
    from schemas import User, UserCreate, UserUpdate
    from services import UserService
    from services._base import OffsetPagination


class UserController(Controller):
    """User Account Controller."""

    path = "/api/users"
    tags = ["User Accounts"]
    guards = [security.requires_active_user]

    # Service injection
    dependencies = {
        "users_service": Provide(
            deps.provide_users_service,
            sync_to_thread=False
        ),
    } | create_filter_dependencies({
        "id_filter": UUID,
        "search": "name,email",  # Search in these fields
        "pagination_type": "limit_offset",
        "pagination_size": 20,
        "created_at": True,  # Enable date filtering
        "updated_at": True,
        "sort_field": "name",
        "sort_order": "asc",
    })

    @get(
        operation_id="ListUsers",
        summary="List all users",
        description="Retrieve paginated list of users with filtering"
    )
    async def list_users(
        self,
        users_service: UserService,
        filters: Annotated[
            list[FilterTypes],
            Dependency(skip_validation=True)
        ]
    ) -> OffsetPagination[User]:
        """List users with pagination and filtering."""
        return await users_service.list_users(*filters)

    @get(
        operation_id="GetUser",
        path="/{user_id:uuid}",
        summary="Get user by ID"
    )
    async def get_user(
        self,
        users_service: UserService,
        user_id: Annotated[
            UUID,
            Parameter(
                title="User ID",
                description="The user to retrieve"
            )
        ],
    ) -> User:
        """Get a single user by ID."""
        return await users_service.get_user(user_id)

    @post(
        operation_id="CreateUser",
        guards=[security.requires_superuser],
        summary="Create new user"
    )
    async def create_user(
        self,
        users_service: UserService,
        data: UserCreate
    ) -> User:
        """Create a new user account."""
        return await users_service.create_user(data)

    @patch(
        operation_id="UpdateUser",
        path="/{user_id:uuid}",
        guards=[security.requires_superuser],
        summary="Update user"
    )
    async def update_user(
        self,
        data: UserUpdate,
        users_service: UserService,
        user_id: Annotated[UUID, Parameter(title="User ID")],
    ) -> User:
        """Update an existing user."""
        return await users_service.update_user(user_id, data)

    @delete(
        operation_id="DeleteUser",
        path="/{user_id:uuid}",
        guards=[security.requires_superuser],
        summary="Delete user"
    )
    async def delete_user(
        self,
        users_service: UserService,
        user_id: Annotated[UUID, Parameter(title="User ID")],
    ) -> None:
        """Delete a user from the system."""
        await users_service.delete_user(user_id)

    @post(
        operation_id="BulkDeactivateUsers",
        path="/bulk-deactivate",
        guards=[security.requires_superuser]
    )
    async def bulk_deactivate(
        self,
        users_service: UserService,
        data: BulkUserIds
    ) -> BulkOperationResult:
        """Deactivate multiple users at once."""
        count = await users_service.bulk_deactivate(data.user_ids)
        return BulkOperationResult(affected_count=count)
```

### Nested Routes and Relationships

```python
class TeamMemberController(Controller):
    """Team member management."""

    path = "/api/teams/{team_id:uuid}/members"
    tags = ["Team Members"]
    guards = [security.requires_team_membership]

    dependencies = {
        "team_service": Provide(deps.provide_team_service),
        "member_service": Provide(deps.provide_team_member_service),
    }

    @get(operation_id="ListTeamMembers")
    async def list_members(
        self,
        team_id: UUID,
        member_service: TeamMemberService,
        filters: Annotated[list[FilterTypes], Dependency(skip_validation=True)]
    ) -> OffsetPagination[TeamMember]:
        """List team members."""
        return await member_service.list_by_team(team_id, *filters)

    @post(
        operation_id="AddTeamMember",
        guards=[security.requires_team_admin]
    )
    async def add_member(
        self,
        team_id: UUID,
        data: AddTeamMember,
        member_service: TeamMemberService
    ) -> TeamMember:
        """Add member to team."""
        return await member_service.add_member(team_id, data)

    @patch(
        operation_id="UpdateMemberRole",
        path="/{user_id:uuid}/role",
        guards=[security.requires_team_admin]
    )
    async def update_role(
        self,
        team_id: UUID,
        user_id: UUID,
        data: UpdateMemberRole,
        member_service: TeamMemberService
    ) -> TeamMember:
        """Update member's role in team."""
        return await member_service.update_role(team_id, user_id, data.role)

    @delete(
        operation_id="RemoveTeamMember",
        path="/{user_id:uuid}",
        guards=[security.requires_team_admin]
    )
    async def remove_member(
        self,
        team_id: UUID,
        user_id: UUID,
        member_service: TeamMemberService
    ) -> None:
        """Remove member from team."""
        await member_service.remove_member(team_id, user_id)
```

## Authentication and Security

### JWT Authentication Setup

```python
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from litestar.exceptions import PermissionDeniedException
from litestar.security.jwt import OAuth2PasswordBearerAuth, Token

from schemas import User
from config import db_manager
from lib.settings import get_settings
from server import deps

if TYPE_CHECKING:
    from litestar.connection import ASGIConnection, Request
    from litestar.handlers.base import BaseRouteHandler

settings = get_settings()


async def current_user_from_token(
    token: Token,
    connection: ASGIConnection[Any, Any, Any, Any]
) -> User | None:
    """Retrieve user from JWT token."""
    service = deps.provide_users_service(
        db_manager.provide_async_request_session(
            "db_session",
            connection.app.state,
            connection.scope
        )
    )

    user = await service.driver.select_one_or_none(
        db_manager.get_sql("get-user-by-id"),
        user_id=token.extras["user_id"],
        schema_type=User
    )

    return user if user and user.is_active else None


def create_access_token(
    user_id: str,
    email: str,
    is_superuser: bool = False,
    is_verified: bool = False,
    auth_method: str = "password",
) -> str:
    """Create JWT access token."""
    token = Token(
        sub=email,
        exp=datetime.now(UTC) + timedelta(hours=1),
        extras={
            "user_id": user_id,
            "is_superuser": is_superuser,
            "is_verified": is_verified,
            "auth_method": auth_method,
        },
    )
    return token.encode(
        secret=settings.app.SECRET_KEY,
        algorithm=settings.app.JWT_ENCRYPTION_ALGORITHM
    )


# Configure OAuth2 authentication
auth = OAuth2PasswordBearerAuth[User](
    retrieve_user_handler=current_user_from_token,
    token_secret=settings.app.SECRET_KEY,
    token_url="/api/access/login",
    exclude=[
        "/api/health",
        "/api/access/login",
        "/api/access/signup",
        "^/schema",
        "^/public/",
    ],
)
```

### Guard Functions

Guards protect routes based on user permissions:

```python
def requires_active_user(
    connection: ASGIConnection[Any, User, Token, Any],
    _: BaseRouteHandler
) -> None:
    """Verify user is active."""
    if not connection.user.is_active:
        raise PermissionDeniedException("Inactive account")


def requires_verified_user(
    connection: ASGIConnection[Any, User, Token, Any],
    _: BaseRouteHandler
) -> None:
    """Verify user email is verified."""
    if not connection.user.is_verified:
        raise PermissionDeniedException("Email not verified")


def requires_superuser(
    connection: ASGIConnection[Any, User, Token, Any],
    _: BaseRouteHandler
) -> None:
    """Verify user has superuser role."""
    if not any(
        role.slug == "superuser"
        for role in connection.user.roles
    ):
        raise PermissionDeniedException("Insufficient privileges")


def requires_team_membership(
    connection: ASGIConnection[Any, User, Token, Any],
    _: BaseRouteHandler
) -> None:
    """Verify user is member of the team."""
    team_id = connection.path_params["team_id"]

    # Superusers always have access
    is_superuser = any(
        role.slug == "superuser"
        for role in connection.user.roles
    )

    # Check team membership
    is_member = any(
        membership.team_id == team_id
        for membership in connection.user.teams
    )

    if not (is_superuser or is_member):
        raise PermissionDeniedException("Not a team member")


def requires_team_admin(
    connection: ASGIConnection[Any, User, Token, Any],
    _: BaseRouteHandler
) -> None:
    """Verify user is team admin."""
    team_id = connection.path_params["team_id"]

    # Superusers always have access
    is_superuser = any(
        role.slug == "superuser"
        for role in connection.user.roles
    )

    # Check for admin role in team
    is_admin = any(
        membership.team_id == team_id and membership.role == "admin"
        for membership in connection.user.teams
    )

    if not (is_superuser or is_admin):
        raise PermissionDeniedException("Admin access required")
```

### Login Controller

```python
class AccessController(Controller):
    """Authentication endpoints."""

    tags = ["Authentication"]

    dependencies = {
        "users_service": Provide(deps.provide_users_service),
    }

    @post(
        operation_id="Login",
        path="/api/access/login",
        exclude_from_auth=True
    )
    async def login(
        self,
        users_service: UserService,
        data: Annotated[
            AccountLogin,
            Body(
                title="OAuth2 Login",
                media_type=RequestEncodingType.URL_ENCODED
            )
        ],
    ) -> Response[OAuth2Login]:
        """Authenticate user and return token."""
        user = await users_service.authenticate(
            data.username,  # Email
            data.password
        )

        # Create token
        access_token = create_access_token(
            user_id=str(user.id),
            email=user.email,
            is_superuser=user.is_superuser,
            is_verified=user.is_verified
        )

        return Response(
            OAuth2Login(
                access_token=access_token,
                token_type="bearer"
            )
        )

    @post(
        operation_id="Signup",
        path="/api/access/signup",
        exclude_from_auth=True
    )
    async def signup(
        self,
        request: Request[User, Token, Any],
        users_service: UserService,
        data: AccountRegister,
    ) -> User:
        """Register new user account."""
        user = await users_service.create_user(data)

        # Emit event for other services
        request.app.emit(
            event_id="user_created",
            user_id=user.id
        )

        return user

    @post(
        operation_id="Logout",
        path="/api/access/logout"
    )
    async def logout(
        self,
        request: Request[User, Token, Any]
    ) -> Response[Message]:
        """Logout current user."""
        request.cookies.pop(auth.key, None)
        request.clear_session()

        response = Response(
            Message(message="Logged out successfully"),
            status_code=200
        )
        response.delete_cookie(auth.key)

        return response
```

## Filters and Pagination

### Filter Types

SQLSpec provides various filter types:

```python
from sqlspec.core.filters import (
    # Pagination filters
    LimitOffsetFilter,
    OffsetPagination,

    # Search filters
    SearchFilter,
    NotInSearchFilter,

    # Collection filters
    InCollectionFilter,
    NotInCollectionFilter,
    AnyCollectionFilter,
    NotAnyCollectionFilter,

    # Date filters
    BeforeAfterFilter,
    OnBeforeAfterFilter,

    # Sorting
    OrderByFilter,

    # Base types
    StatementFilter,
    PaginationFilter,
)
```

### Creating Filter Dependencies

```python
from sqlspec.extensions.litestar.providers import create_filter_dependencies

# In your controller
dependencies = create_filter_dependencies({
    # Enable ID filtering
    "id_filter": UUID,

    # Enable text search on specific fields
    "search": "name,email,description",

    # Configure pagination
    "pagination_type": "limit_offset",
    "pagination_size": 20,

    # Enable date filtering
    "created_at": True,
    "updated_at": True,

    # Configure default sorting
    "sort_field": "created_at",
    "sort_order": "desc",

    # Enable status filtering
    "is_active": bool,
    "is_verified": bool,
})
```

### Using Filters in Services

```python
class UserService(SQLSpecService):

    async def list_users(
        self,
        *filters: StatementFilter
    ) -> OffsetPagination[User]:
        """List users with dynamic filtering."""

        # Extract specific filters
        limit_offset = self.find_filter(LimitOffsetFilter, filters)
        search = self.find_filter(SearchFilter, filters)
        order_by = self.find_filter(OrderByFilter, filters)
        date_filter = self.find_filter(BeforeAfterFilter, filters)

        # Build query dynamically
        query = sql.select("*").from_("user_account")

        # Apply search filter
        if search and search.search_value:
            query = query.where(
                sql.or_(
                    sql.column("name").ilike(f"%{search.search_value}%"),
                    sql.column("email").ilike(f"%{search.search_value}%")
                )
            )

        # Apply date filter
        if date_filter:
            if date_filter.after:
                query = query.where("created_at >= :after", after=date_filter.after)
            if date_filter.before:
                query = query.where("created_at <= :before", before=date_filter.before)

        # Apply ordering
        if order_by:
            query = query.order_by(order_by.order_by)
        else:
            query = query.order_by("created_at DESC")

        # Execute with pagination
        return await self.paginate(
            query,
            *filters,
            schema_type=User
        )
```

### Custom Filters

Create custom filters for specific needs:

```python
from dataclasses import dataclass
from sqlspec.core.filters import StatementFilter


@dataclass
class TeamFilter(StatementFilter):
    """Filter by team membership."""

    team_id: UUID
    role: str | None = None

    def apply(self, statement):
        """Apply team filter to query."""
        statement = statement.where_eq("team_id", self.team_id)
        if self.role:
            statement = statement.where_eq("role", self.role)
        return statement


@dataclass
class StatusFilter(StatementFilter):
    """Filter by multiple status fields."""

    is_active: bool | None = None
    is_verified: bool | None = None
    is_superuser: bool | None = None

    def apply(self, statement):
        """Apply status filters."""
        if self.is_active is not None:
            statement = statement.where_eq("is_active", self.is_active)
        if self.is_verified is not None:
            statement = statement.where_eq("is_verified", self.is_verified)
        if self.is_superuser is not None:
            statement = statement.where_eq("is_superuser", self.is_superuser)
        return statement
```

## Dependency Injection

### Service Providers

Define provider functions for each service:

```python
# server/deps.py
from typing import TYPE_CHECKING

from services import (
    UserService,
    TeamService,
    RoleService,
    TagService,
    TeamMemberService,
    UserRoleService,
    EmailVerificationService,
    PasswordService,
)

if TYPE_CHECKING:
    from sqlspec.driver import AsyncDriverAdapterBase


def provide_users_service(
    db_session: AsyncDriverAdapterBase
) -> UserService:
    """Provide user service with database driver."""
    return UserService(db_session)


def provide_team_service(
    db_session: AsyncDriverAdapterBase
) -> TeamService:
    """Provide team service with database driver."""
    return TeamService(db_session)


def provide_role_service(
    db_session: AsyncDriverAdapterBase
) -> RoleService:
    """Provide role service with database driver."""
    return RoleService(db_session)


def provide_tag_service(
    db_session: AsyncDriverAdapterBase
) -> TagService:
    """Provide tag service with database driver."""
    return TagService(db_session)


def provide_team_member_service(
    db_session: AsyncDriverAdapterBase
) -> TeamMemberService:
    """Provide team member service with database driver."""
    return TeamMemberService(db_session)
```

### Using Dependencies in Controllers

```python
class UserController(Controller):
    """User management endpoints."""

    # Define dependencies at class level
    dependencies = {
        "users_service": Provide(
            deps.provide_users_service,
            sync_to_thread=False
        ),
        "email_service": Provide(
            deps.provide_email_service,
            sync_to_thread=False
        ),
    }

    @post(operation_id="CreateUser")
    async def create_user(
        self,
        users_service: UserService,  # Injected automatically
        email_service: EmailService,  # Injected automatically
        data: UserCreate
    ) -> User:
        """Create user and send welcome email."""
        user = await users_service.create_user(data)
        await email_service.send_welcome(user.email)
        return user
```

### Global Dependencies

Configure application-wide dependencies:

```python
# server/core.py
class ApplicationCore(InitPluginProtocol):
    """Application core configuration."""

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        """Configure application."""

        # Global dependencies
        dependencies = {
            "current_user": Provide(
                security.provide_user,
                sync_to_thread=False
            ),
            "db_session": Provide(
                db_manager.provide_async_request_session
            ),
        }

        app_config.dependencies.update(dependencies)

        return app_config
```

### Nested Dependencies

Dependencies can depend on other dependencies:

```python
def provide_notification_service(
    db_session: AsyncDriverAdapterBase,
    email_service: EmailService,  # Nested dependency
    push_service: PushService,    # Nested dependency
) -> NotificationService:
    """Provide notification service with dependencies."""
    return NotificationService(
        driver=db_session,
        email=email_service,
        push=push_service
    )
```

## Schema and Data Transfer Objects

### Base Schema Classes

```python
# schemas/base.py
from typing import Any

import msgspec
from pydantic import BaseModel as _BaseModel
from pydantic import ConfigDict
from sqlspec.utils.text import camelize


class BaseStruct(msgspec.Struct):
    """Base msgspec struct for high-performance serialization."""

    def to_dict(self) -> dict[str, Any]:
        """Convert struct to dictionary."""
        return {
            f: getattr(self, f)
            for f in self.__struct_fields__
            if getattr(self, f, None) != msgspec.UNSET
        }


class CamelizedBaseStruct(BaseStruct, rename="camel"):
    """Base struct with camelCase field names."""
    pass


class BaseSchema(_BaseModel):
    """Base Pydantic schema."""

    model_config = ConfigDict(
        validate_assignment=True,
        from_attributes=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )


class CamelizedBaseSchema(BaseSchema):
    """Base schema with camelCase field names."""

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=camelize
    )
```

### User Schemas

```python
# schemas/_accounts.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from schemas.base import CamelizedBaseSchema


class UserBase(CamelizedBaseSchema):
    """Base user schema."""

    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)
    avatar_url: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating users."""

    password: str = Field(..., min_length=8, max_length=100)
    initial_team_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Ensure password meets requirements."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain digit")
        return v


class UserUpdate(CamelizedBaseSchema):
    """Schema for updating users."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    avatar_url: Optional[str] = None


class TeamMembership(CamelizedBaseSchema):
    """Team membership info."""

    team_id: UUID
    team_name: str
    role: str
    is_owner: bool
    joined_at: datetime


class RoleAssignment(CamelizedBaseSchema):
    """Role assignment info."""

    role_id: UUID
    role_name: str
    role_slug: str
    assigned_at: datetime


class User(UserBase):
    """Full user schema with relationships."""

    id: UUID
    is_active: bool
    is_verified: bool
    is_superuser: bool
    has_password: bool
    verified_at: Optional[datetime]
    last_login: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    # Relationships
    teams: list[TeamMembership] = Field(default_factory=list)
    roles: list[RoleAssignment] = Field(default_factory=list)

    @property
    def full_name(self) -> str:
        """Get user's full display name."""
        return self.name or self.email

    def has_role(self, role_slug: str) -> bool:
        """Check if user has specific role."""
        return any(r.role_slug == role_slug for r in self.roles)

    def is_team_member(self, team_id: UUID) -> bool:
        """Check if user is member of team."""
        return any(t.team_id == team_id for t in self.teams)
```

### Request/Response Schemas

```python
# schemas/_accounts.py (continued)
class AccountLogin(CamelizedBaseSchema):
    """OAuth2 compatible login schema."""

    username: EmailStr  # Email in our case
    password: str


class AccountRegister(UserCreate):
    """Registration schema."""

    terms_accepted: bool = Field(..., const=True)
    newsletter_opt_in: bool = False


class ProfileUpdate(CamelizedBaseSchema):
    """Schema for users updating their own profile."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    avatar_url: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)
    timezone: Optional[str] = None


class PasswordChange(CamelizedBaseSchema):
    """Schema for password changes."""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)
    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, values: dict) -> str:
        """Ensure passwords match."""
        if "new_password" in values and v != values["new_password"]:
            raise ValueError("Passwords do not match")
        return v


class BulkUserIds(CamelizedBaseSchema):
    """Schema for bulk operations on users."""

    user_ids: list[UUID] = Field(..., min_items=1, max_items=100)


class BulkOperationResult(CamelizedBaseSchema):
    """Result of bulk operation."""

    affected_count: int
    success: bool = True
    errors: list[str] = Field(default_factory=list)
```

## Transaction Management

### Using Transactions in Services

```python
class TeamService(SQLSpecService):
    """Team management service."""

    async def create_team_with_members(
        self,
        data: TeamCreate,
        member_emails: list[str]
    ) -> Team:
        """Create team and add initial members atomically."""

        # Use transaction context manager
        async with self.begin_transaction():
            # Create team
            team = await self.driver.select_one(
                sql.insert("team")
                .values(
                    name=data.name,
                    description=data.description,
                    slug=await self._get_unique_slug(data.name)
                )
                .returning("*"),
                schema_type=Team
            )

            # Add creator as owner
            await self.driver.execute(
                sql.insert("team_member")
                .values(
                    team_id=team.id,
                    user_id=data.creator_id,
                    role="owner",
                    is_owner=True
                )
            )

            # Add other members
            for email in member_emails:
                user = await self.driver.select_one_or_none(
                    sql.select("id").from_("user_account")
                    .where_eq("email", email)
                )

                if user:
                    await self.driver.execute(
                        sql.insert("team_member")
                        .values(
                            team_id=team.id,
                            user_id=user["id"],
                            role="member"
                        )
                    )

            # Transaction commits here if no errors
            return team
        # Transaction rolls back if any error occurred

    async def transfer_ownership(
        self,
        team_id: UUID,
        new_owner_id: UUID
    ) -> None:
        """Transfer team ownership atomically."""

        # Manual transaction control
        await self.begin()
        try:
            # Remove old owner flag
            await self.driver.execute(
                sql.update("team_member")
                .set(is_owner=False, role="admin")
                .where_eq("team_id", team_id)
                .where_eq("is_owner", True)
            )

            # Set new owner
            await self.driver.execute(
                sql.update("team_member")
                .set(is_owner=True, role="owner")
                .where_eq("team_id", team_id)
                .where_eq("user_id", new_owner_id)
            )

            # Update team record
            await self.driver.execute(
                sql.update("team")
                .set(
                    owner_id=new_owner_id,
                    updated_at=sql.raw("NOW()")
                )
                .where_eq("id", team_id)
            )

            await self.commit()
        except Exception as e:
            await self.rollback()
            raise ValueError(f"Ownership transfer failed: {e}")
```

### Nested Transactions

```python
class OrderService(SQLSpecService):
    """Order management service."""

    async def process_order(
        self,
        order_id: UUID
    ) -> Order:
        """Process order with nested transactions."""

        async with self.begin_transaction():
            # Update order status
            order = await self.driver.select_one(
                sql.update("orders")
                .set(status="processing")
                .where_eq("id", order_id)
                .returning("*"),
                schema_type=Order
            )

            # Process each item
            for item in order.items:
                # This could be in its own service with transaction
                await self._process_order_item(item)

            # Update inventory
            await self._update_inventory(order.items)

            # Create invoice
            await self._create_invoice(order)

            # Mark as processed
            order = await self.driver.select_one(
                sql.update("orders")
                .set(
                    status="processed",
                    processed_at=sql.raw("NOW()")
                )
                .where_eq("id", order_id)
                .returning("*"),
                schema_type=Order
            )

            return order
```

## Testing Strategies

### Service Testing

```python
# tests/test_user_service.py
import pytest
from uuid import uuid4

from services import UserService
from schemas import UserCreate


@pytest.fixture
async def user_service(db_session):
    """Create user service with test database."""
    return UserService(db_session)


@pytest.mark.asyncio
async def test_create_user(user_service):
    """Test user creation."""
    data = UserCreate(
        email="test@example.com",
        name="Test User",
        password="SecurePass123!"
    )

    user = await user_service.create_user(data)

    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.name == "Test User"
    assert user.has_password is True


@pytest.mark.asyncio
async def test_authenticate_user(user_service):
    """Test user authentication."""
    # Create user first
    data = UserCreate(
        email="auth@example.com",
        name="Auth User",
        password="SecurePass123!"
    )
    await user_service.create_user(data)

    # Test authentication
    user = await user_service.authenticate(
        "auth@example.com",
        "SecurePass123!"
    )
    assert user.email == "auth@example.com"

    # Test invalid password
    with pytest.raises(PermissionDeniedException):
        await user_service.authenticate(
            "auth@example.com",
            "WrongPassword"
        )


@pytest.mark.asyncio
async def test_list_users_with_filters(user_service):
    """Test listing users with pagination."""
    # Create test users
    for i in range(25):
        await user_service.create_user(
            UserCreate(
                email=f"user{i}@example.com",
                name=f"User {i}",
                password="SecurePass123!"
            )
        )

    # Test pagination
    from services._base import LimitOffsetFilter

    result = await user_service.list_users(
        LimitOffsetFilter(limit=10, offset=0)
    )

    assert len(result.items) == 10
    assert result.total == 25
    assert result.limit == 10
    assert result.offset == 0
```

### Controller Testing

```python
# tests/test_user_controller.py
import pytest
from httpx import AsyncClient
from litestar import Litestar
from litestar.testing import create_test_client


@pytest.fixture
def app() -> Litestar:
    """Create test application."""
    from server.core import ApplicationCore
    from litestar import Litestar

    return Litestar(
        route_handlers=[],
        plugins=[ApplicationCore()]
    )


@pytest.fixture
async def client(app):
    """Create test client."""
    async with AsyncClient(
        app=app,
        base_url="http://testserver"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_create_user_endpoint(client, auth_headers):
    """Test user creation via API."""
    response = await client.post(
        "/api/users",
        json={
            "email": "newuser@example.com",
            "name": "New User",
            "password": "SecurePass123!"
        },
        headers=auth_headers
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["name"] == "New User"


@pytest.mark.asyncio
async def test_list_users_pagination(client, auth_headers):
    """Test user listing with pagination."""
    response = await client.get(
        "/api/users?limit=5&offset=10",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["limit"] == 5
    assert data["offset"] == 10
```

## Best Practices and Patterns

### 1. Service Layer Best Practices

- **Single Responsibility**: Each service handles one domain entity
- **Dependency Injection**: Always inject services via DI
- **Transaction Boundaries**: Define clear transaction boundaries
- **Error Handling**: Use domain-specific exceptions
- **Validation**: Validate at the schema level, not service

### 2. SQL Query Organization

- **Naming Convention**: Use `{action}-{entity}[-{qualifier}]`
- **Parameter Naming**: Use consistent parameter names
- **Comments**: Document complex queries
- **Performance**: Add appropriate indexes
- **Consistency**: Use same patterns across queries

### 3. Controller Patterns

- **Thin Controllers**: Keep business logic in services
- **Guard Composition**: Combine guards for complex permissions
- **Error Responses**: Use consistent error response format
- **Documentation**: Always include OpenAPI documentation
- **Filtering**: Use standard filter patterns

### 4. Security Considerations

- **Password Hashing**: Always use argon2 or bcrypt
- **JWT Expiry**: Use short-lived tokens with refresh
- **Rate Limiting**: Implement rate limiting on sensitive endpoints
- **CORS**: Configure CORS properly for production
- **SQL Injection**: Always use parameterized queries

### 5. Performance Optimization

- **Connection Pooling**: Configure pool sizes appropriately
- **Query Optimization**: Use EXPLAIN ANALYZE for slow queries
- **Caching**: Implement caching for frequently accessed data
- **Pagination**: Always paginate large result sets
- **Async Operations**: Use async for I/O operations

## Complete Example: Building a Feature

Let's build a complete blog post feature with comments:

### 1. Database Schema

```sql
-- db/migrations/0002_add_blog_posts.sql
CREATE TABLE post (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    author_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    slug VARCHAR(200) UNIQUE NOT NULL,
    content TEXT NOT NULL,
    published BOOLEAN DEFAULT false,
    published_at TIMESTAMPTZ,
    view_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE comment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES post(id) ON DELETE CASCADE,
    author_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES comment(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_deleted BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_post_author ON post(author_id);
CREATE INDEX idx_post_slug ON post(slug);
CREATE INDEX idx_post_published ON post(published, published_at);
CREATE INDEX idx_comment_post ON comment(post_id);
CREATE INDEX idx_comment_author ON comment(author_id);
```

### 2. SQL Queries

```sql
-- db/sql/posts.sql

-- name: create-post
INSERT INTO post (
    author_id, title, slug, content, published, published_at
)
VALUES (
    :author_id, :title, :slug, :content,
    COALESCE(:published, false),
    CASE WHEN :published THEN NOW() ELSE NULL END
)
RETURNING *;

-- name: get-post-with-author
SELECT
    p.*,
    json_build_object(
        'id', u.id,
        'name', u.name,
        'email', u.email,
        'avatar_url', u.avatar_url
    ) as author
FROM post p
JOIN user_account u ON p.author_id = u.id
WHERE p.id = :post_id;

-- name: list-published-posts
SELECT
    p.id, p.title, p.slug, p.published_at, p.view_count,
    u.name as author_name,
    COUNT(DISTINCT c.id) as comment_count
FROM post p
JOIN user_account u ON p.author_id = u.id
LEFT JOIN comment c ON p.id = c.post_id AND c.is_deleted = false
WHERE p.published = true
    AND (:search IS NULL OR (
        p.title ILIKE '%' || :search || '%' OR
        p.content ILIKE '%' || :search || '%'
    ))
GROUP BY p.id, u.name
ORDER BY p.published_at DESC
LIMIT :limit OFFSET :offset;

-- name: update-post-views
UPDATE post
SET view_count = view_count + 1
WHERE id = :post_id;

-- name: add-comment
INSERT INTO comment (
    post_id, author_id, parent_id, content
)
VALUES (
    :post_id, :author_id, :parent_id, :content
)
RETURNING *;

-- name: get-post-comments
WITH RECURSIVE comment_tree AS (
    -- Base case: root comments
    SELECT
        c.*,
        json_build_object(
            'id', u.id,
            'name', u.name,
            'avatar_url', u.avatar_url
        ) as author,
        0 as depth
    FROM comment c
    JOIN user_account u ON c.author_id = u.id
    WHERE c.post_id = :post_id
        AND c.parent_id IS NULL
        AND c.is_deleted = false

    UNION ALL

    -- Recursive case: nested comments
    SELECT
        c.*,
        json_build_object(
            'id', u.id,
            'name', u.name,
            'avatar_url', u.avatar_url
        ) as author,
        ct.depth + 1
    FROM comment c
    JOIN user_account u ON c.author_id = u.id
    JOIN comment_tree ct ON c.parent_id = ct.id
    WHERE c.is_deleted = false
        AND ct.depth < 3  -- Max nesting depth
)
SELECT * FROM comment_tree
ORDER BY created_at ASC;
```

### 3. Schemas

```python
# schemas/_blog.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field, field_validator

from schemas.base import CamelizedBaseSchema


class PostBase(CamelizedBaseSchema):
    """Base post schema."""

    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    published: bool = False


class PostCreate(PostBase):
    """Create post schema."""

    slug: Optional[str] = None

    @field_validator("slug")
    @classmethod
    def generate_slug(cls, v: Optional[str], values: dict) -> str:
        """Generate slug from title if not provided."""
        if not v and "title" in values:
            from sqlspec.utils.text import slugify
            return slugify(values["title"])
        return v


class PostUpdate(CamelizedBaseSchema):
    """Update post schema."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    published: Optional[bool] = None


class Author(CamelizedBaseSchema):
    """Author info schema."""

    id: UUID
    name: str
    email: str
    avatar_url: Optional[str]


class Post(PostBase):
    """Full post schema."""

    id: UUID
    author_id: UUID
    slug: str
    view_count: int
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    # Nested data
    author: Optional[Author] = None
    comment_count: int = 0


class CommentCreate(CamelizedBaseSchema):
    """Create comment schema."""

    content: str = Field(..., min_length=1, max_length=5000)
    parent_id: Optional[UUID] = None


class Comment(CamelizedBaseSchema):
    """Comment schema."""

    id: UUID
    post_id: UUID
    author_id: UUID
    parent_id: Optional[UUID]
    content: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    # Nested
    author: Author
    depth: int = 0
    replies: list["Comment"] = Field(default_factory=list)
```

### 4. Service

```python
# services/_blog.py
from typing import TYPE_CHECKING
from uuid import UUID

from sqlspec import sql
from sqlspec.utils.text import slugify
from sqlspec.utils.type_guards import schema_dump

from schemas import Post, PostCreate, PostUpdate, Comment, CommentCreate
from config import db_manager
from services._base import OffsetPagination, SQLSpecService, StatementFilter

if TYPE_CHECKING:
    from sqlspec.driver import AsyncDriverAdapterBase


class BlogService(SQLSpecService):
    """Blog post and comment management."""

    async def create_post(
        self,
        author_id: UUID,
        data: PostCreate
    ) -> Post:
        """Create a new blog post."""
        post_data = schema_dump(data, exclude_unset=True)

        # Ensure unique slug
        if not post_data.get("slug"):
            post_data["slug"] = await self._get_unique_slug(data.title)

        post_data["author_id"] = author_id

        return await self.driver.select_one(
            db_manager.get_sql("create-post"),
            schema_type=Post,
            **post_data
        )

    async def update_post(
        self,
        post_id: UUID,
        author_id: UUID,
        data: PostUpdate
    ) -> Post:
        """Update a blog post."""
        # Verify ownership
        post = await self.get_post(post_id)
        if post.author_id != author_id:
            raise PermissionDeniedException("Not the post author")

        update_data = schema_dump(data, exclude_unset=True)

        # Handle publishing
        if data.published and not post.published:
            update_data["published_at"] = sql.raw("NOW()")

        await self.driver.execute(
            sql.update("post")
            .set(**update_data, updated_at=sql.raw("NOW()"))
            .where_eq("id", post_id)
        )

        return await self.get_post(post_id)

    async def get_post(
        self,
        post_id: UUID,
        increment_views: bool = False
    ) -> Post:
        """Get a single post with author info."""
        if increment_views:
            await self.driver.execute(
                db_manager.get_sql("update-post-views"),
                post_id=post_id
            )

        return await self.get_or_404(
            db_manager.get_sql("get-post-with-author"),
            post_id=post_id,
            schema_type=Post,
            error_message=f"Post {post_id} not found"
        )

    async def list_published_posts(
        self,
        *filters: StatementFilter
    ) -> OffsetPagination[Post]:
        """List published posts with pagination."""
        return await self.paginate(
            db_manager.get_sql("list-published-posts"),
            *filters,
            schema_type=Post
        )

    async def add_comment(
        self,
        post_id: UUID,
        author_id: UUID,
        data: CommentCreate
    ) -> Comment:
        """Add a comment to a post."""
        # Verify post exists and is published
        post = await self.get_post(post_id)
        if not post.published:
            raise ValueError("Cannot comment on unpublished post")

        # Verify parent comment if provided
        if data.parent_id:
            parent = await self.driver.select_one_or_none(
                sql.select("id", "post_id")
                .from_("comment")
                .where_eq("id", data.parent_id)
            )
            if not parent or parent["post_id"] != post_id:
                raise ValueError("Invalid parent comment")

        return await self.driver.select_one(
            db_manager.get_sql("add-comment"),
            post_id=post_id,
            author_id=author_id,
            parent_id=data.parent_id,
            content=data.content,
            schema_type=Comment
        )

    async def get_post_comments(
        self,
        post_id: UUID
    ) -> list[Comment]:
        """Get all comments for a post in tree structure."""
        flat_comments = await self.driver.select(
            db_manager.get_sql("get-post-comments"),
            post_id=post_id,
            schema_type=Comment
        )

        # Build tree structure
        comment_map = {c.id: c for c in flat_comments}
        roots = []

        for comment in flat_comments:
            if comment.parent_id and comment.parent_id in comment_map:
                parent = comment_map[comment.parent_id]
                parent.replies.append(comment)
            elif not comment.parent_id:
                roots.append(comment)

        return roots

    async def delete_comment(
        self,
        comment_id: UUID,
        author_id: UUID
    ) -> None:
        """Soft delete a comment."""
        # Verify ownership
        comment = await self.driver.select_one(
            sql.select("author_id")
            .from_("comment")
            .where_eq("id", comment_id)
        )

        if comment["author_id"] != author_id:
            raise PermissionDeniedException("Not the comment author")

        # Soft delete
        await self.driver.execute(
            sql.update("comment")
            .set(is_deleted=True, content="[deleted]")
            .where_eq("id", comment_id)
        )

    async def _get_unique_slug(self, title: str) -> str:
        """Generate unique slug for post."""
        base_slug = slugify(title)
        slug = base_slug
        counter = 1

        while await self.exists(
            sql.select("id").from_("post").where_eq("slug", slug)
        ):
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug
```

### 5. Controller

```python
# server/routes/blog.py
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from litestar import Controller, delete, get, patch, post
from litestar.di import Provide
from litestar.params import Dependency, Parameter

from server import deps, security
from services import FilterTypes

if TYPE_CHECKING:
    from schemas import (
        Post, PostCreate, PostUpdate,
        Comment, CommentCreate, User
    )
    from services import BlogService
    from services._base import OffsetPagination


class BlogController(Controller):
    """Blog post management."""

    path = "/api/posts"
    tags = ["Blog"]

    dependencies = {
        "blog_service": Provide(deps.provide_blog_service),
    }

    @get(
        operation_id="ListPosts",
        summary="List published posts"
    )
    async def list_posts(
        self,
        blog_service: BlogService,
        filters: Annotated[list[FilterTypes], Dependency(skip_validation=True)]
    ) -> OffsetPagination[Post]:
        """List all published blog posts."""
        return await blog_service.list_published_posts(*filters)

    @get(
        operation_id="GetPost",
        path="/{post_id:uuid}",
        summary="Get single post"
    )
    async def get_post(
        self,
        blog_service: BlogService,
        post_id: UUID,
        increment_views: bool = True
    ) -> Post:
        """Get a single blog post."""
        return await blog_service.get_post(
            post_id,
            increment_views=increment_views
        )

    @post(
        operation_id="CreatePost",
        guards=[security.requires_active_user],
        summary="Create new post"
    )
    async def create_post(
        self,
        blog_service: BlogService,
        current_user: User,
        data: PostCreate
    ) -> Post:
        """Create a new blog post."""
        return await blog_service.create_post(
            current_user.id,
            data
        )

    @patch(
        operation_id="UpdatePost",
        path="/{post_id:uuid}",
        guards=[security.requires_active_user],
        summary="Update post"
    )
    async def update_post(
        self,
        blog_service: BlogService,
        current_user: User,
        post_id: UUID,
        data: PostUpdate
    ) -> Post:
        """Update an existing post."""
        return await blog_service.update_post(
            post_id,
            current_user.id,
            data
        )

    @get(
        operation_id="GetPostComments",
        path="/{post_id:uuid}/comments",
        summary="Get post comments"
    )
    async def get_comments(
        self,
        blog_service: BlogService,
        post_id: UUID
    ) -> list[Comment]:
        """Get all comments for a post."""
        return await blog_service.get_post_comments(post_id)

    @post(
        operation_id="AddComment",
        path="/{post_id:uuid}/comments",
        guards=[security.requires_verified_user],
        summary="Add comment"
    )
    async def add_comment(
        self,
        blog_service: BlogService,
        current_user: User,
        post_id: UUID,
        data: CommentCreate
    ) -> Comment:
        """Add a comment to a post."""
        return await blog_service.add_comment(
            post_id,
            current_user.id,
            data
        )

    @delete(
        operation_id="DeleteComment",
        path="/comments/{comment_id:uuid}",
        guards=[security.requires_active_user],
        summary="Delete comment"
    )
    async def delete_comment(
        self,
        blog_service: BlogService,
        current_user: User,
        comment_id: UUID
    ) -> None:
        """Delete a comment."""
        await blog_service.delete_comment(
            comment_id,
            current_user.id
        )
```

### 6. Register Everything

```python
# server/core.py
def on_app_init(self, app_config: AppConfig) -> AppConfig:
    """Configure application."""

    # Add blog controller to routes
    app_config.route_handlers.extend([
        routes.BlogController,
        # ... other controllers
    ])

    # Add blog service to signature namespace
    app_config.signature_namespace.update({
        "BlogService": BlogService,
        # ... other services
    })

    return app_config

# server/deps.py
def provide_blog_service(
    db_session: AsyncDriverAdapterBase
) -> BlogService:
    """Provide blog service."""
    return BlogService(db_session)
```

## Conclusion

This guide provides a comprehensive foundation for building web applications with SQLSpec and Litestar. The key principles to remember:

1. **Separation of Concerns**: Keep business logic in services, HTTP handling in controllers
2. **Type Safety**: Use Pydantic/msgspec schemas for validation and documentation
3. **SQL Organization**: Use named queries for complex SQL, builders for dynamic queries
4. **Transaction Management**: Define clear transaction boundaries for data consistency
5. **Security First**: Implement proper authentication, authorization, and input validation
6. **Performance**: Use async operations, connection pooling, and pagination
7. **Testing**: Write comprehensive tests for services and controllers
8. **Documentation**: Use OpenAPI annotations and docstrings

The combination of SQLSpec's powerful SQL abstraction and Litestar's high-performance ASGI framework provides an excellent foundation for building scalable, maintainable web applications while keeping close to the metal when it comes to database operations.
