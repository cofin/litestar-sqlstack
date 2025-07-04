# SQLSpec Migration Plan

This document outlines the detailed migration plan from Advanced-Alchemy/SQLAlchemy to SQLSpec.

## Current State Analysis

The codebase is partially migrated:

- ✅ `config.py` already uses SQLSpec configuration
- ❌ `plugins.py` still imports Advanced-Alchemy
- ❌ Services still use Advanced-Alchemy patterns
- ❌ Routes still import from Advanced-Alchemy
- ❌ Incorrect imports referencing "app" instead of "sqlstack"

## Phase 1: Configuration Migration

### 1.1 Fix plugins.py

**File:** `/sqlstack/server/plugins.py`

**REMOVE:**

```python
from advanced_alchemy.extensions.litestar import SQLAlchemyPlugin
from app import config

alchemy = SQLAlchemyPlugin(config=config.alchemy)
```

**REPLACE WITH:**

```python
from sqlstack import config
# Remove alchemy plugin - SQLSpec is configured in config.py
```

**ALSO FIX:**

- Change `from app import config` to `from sqlstack import config`
- Remove references to `config.vite` and `config.saq` if they don't exist in sqlstack config

### 1.2 Remove Advanced-Alchemy Configuration

**Check and remove from settings.py or any config files:**

- Any `AlchemySettings` class
- SQLAlchemy-specific configuration like `echo_pool`, `pool_recycle`
- Migration to use SQLSpec's connection pool configuration

## Phase 2: Services Migration

### 2.1 Base Service Pattern

**Create/Update:** `/sqlstack/services/_base.py`

The file already exists with SQLSpec patterns. Services need to migrate from:

**FROM (Advanced-Alchemy pattern):**

```python
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from litestar.plugins.sqlalchemy import repository

class TeamService(service.SQLAlchemyAsyncRepositoryService[m.Team]):
    class Repo(repository.SQLAlchemyAsyncSlugRepository[m.Team]):
        model_type = m.Team
    
    repository_type = Repo
```

**TO (SQLSpec pattern):**

```python
from sqlspec.adapters.asyncpg import AsyncpgDriver
from sqlstack.services._base import SqlspecService, OffsetPagination

class TeamService(SqlspecService[AsyncpgDriver]):
    async def create(self, data: s.TeamCreate) -> s.Team:
        stmt = sg.Expression.insert("teams", self.generate_binds(data), returning="*")
        obj = await self.driver.insert_update_delete_returning(stmt.sql(), **schema_dump(data))
        return self.to_schema(obj, schema_type=s.Team)
```

### 2.2 Service Files to Migrate

All files in `/sqlstack/services/` that import Advanced-Alchemy:

- `_teams.py`
- `_user_oauth_accounts.py`
- `_user_roles.py`
- `_tags.py`
- `_team_files.py`
- `_team_invitations.py`
- `_team_members.py`

**For each service, REMOVE:**

- `from advanced_alchemy.utils.text import slugify`
- `from litestar.plugins.sqlalchemy import repository, service`
- `from advanced_alchemy.service import ModelDictT`
- Repository class definitions
- `repository_type` assignments
- `match_fields` assignments

**REPLACE WITH:**

- Direct SQL operations using `sqlglot` for query building
- `self.driver` methods for database operations
- `self.to_schema()` for type conversions
- Manual implementation of slug generation if needed

### 2.3 Common Service Methods Pattern

**CREATE:**

```python
async def create(self, data: SchemaType) -> SchemaType:
    stmt = sg.Expression.insert("table_name", self.generate_binds(data), returning="*")
    obj = await self.driver.insert_update_delete_returning(stmt.sql(), **schema_dump(data))
    return self.to_schema(obj, schema_type=SchemaType)
```

**UPDATE:**

```python
async def update(self, item_id: UUID, data: SchemaUpdate) -> SchemaType:
    bind_data = schema_dump(data)
    bind_data["id"] = item_id
    stmt = sg.Expression.update("table_name", self.generate_binds(bind_data), where="id = :id", returning="*")
    obj = await self.driver.insert_update_delete_returning(stmt.sql(), **bind_data)
    return self.to_schema(obj, schema_type=SchemaType)
```

**LIST with Pagination:**

```python
async def list(self, filters: list[StatementFilter] | None = None) -> OffsetPagination[SchemaType]:
    limit_offset = find_filter(LimitOffset, filters) or LimitOffset(limit=10, offset=0)
    
    count_stmt = "SELECT COUNT(*) FROM table_name"
    total = await self.driver.count(count_stmt)
    
    stmt = f"SELECT * FROM table_name LIMIT :limit OFFSET :offset"
    results = await self.driver.select_many(stmt, limit=limit_offset.limit, offset=limit_offset.offset)
    
    return OffsetPagination(
        items=[self.to_schema(item, schema_type=SchemaType) for item in results],
        total=total,
        limit=limit_offset.limit,
        offset=limit_offset.offset,
    )
```

## Phase 3: Routes Migration

### 3.1 Import Changes

**For all route files, REMOVE:**

```python
from advanced_alchemy.service import FilterTypeT
from advanced_alchemy.service.pagination import OffsetPagination
from sqlalchemy import select
from app import schemas as s
from app.db import models as m
from app.lib.deps import create_service_dependencies
```

**REPLACE WITH:**

```python
from sqlspec.filters import StatementFilter
from sqlstack import schemas as s
from sqlstack.services._base import OffsetPagination
# Remove model imports - use schemas directly
# Remove create_service_dependencies - inject services directly
```

### 3.2 Dependency Injection Pattern

**FROM:**

```python
dependencies = create_service_dependencies(
    TeamService,
    key="teams_service",
    load=[m.Team.tags, m.Team.members],
    filters={"id_filter": UUID},
)
```

**TO:**

```python
# Remove class-level dependencies
# Inject service directly in route handlers:

@get("/api/teams")
async def list_teams(
    self,
    db: AsyncpgDriver,  # Injected via dependency
    current_user: s.User,
    limit: int = 10,
    offset: int = 0,
) -> OffsetPagination[s.Team]:
    service = TeamService(db)
    filters = [LimitOffset(limit=limit, offset=offset)]
    return await service.list(filters=filters)
```

### 3.3 Route Files to Migrate

All files in `/sqlstack/server/routes/` that import Advanced-Alchemy:

- `tag.py`
- `team_invitation.py`
- `team_member.py`
- `team.py`
- `user_role.py`
- `user.py`
- `access.py`
- `roles.py`
- `system.py`

## Phase 4: Database Models to Schemas

Since SQLSpec doesn't use ORM models, all database interactions should use schemas directly:

**REMOVE:**

- All references to `m.Model` (e.g., `m.Team`, `m.User`)
- Model-based queries
- Relationship loading (`load=[...]`)

**USE:**

- Schema classes for type hints (e.g., `s.Team`, `s.User`)
- Direct SQL queries
- Manual JOIN operations when needed

## Phase 5: Utilities and Dependencies

### 5.1 Update deps.py

**File:** `/sqlstack/server/deps.py`

**REMOVE:**

- `create_service_dependencies` function
- Advanced-Alchemy specific dependency factories

**ADD:**

- Direct SQLSpec driver injection
- Service instantiation helpers

### 5.2 Update DTO utilities

**File:** `/sqlstack/utils/dto.py`

**REMOVE:**

- Advanced-Alchemy DTO configurations
- `SQLAlchemyDTOConfig`

**USE:**

- Direct schema validation with Pydantic/msgspec

## Phase 6: Database Operations

### 6.1 Remove Alembic References

**REMOVE:**

- References to Alembic migrations in settings
- `MIGRATION_DDL_VERSION_TABLE` configuration

**USE:**

- SQLSpec's migration approach or raw SQL migrations

### 6.2 Update Event Handlers

Files in `/sqlstack/server/events/`:

- Update to use SQLSpec driver instead of repositories
- Remove ORM-based operations

## Implementation Order

1. **Fix imports** - Update all `from app` to `from sqlstack`
2. **Update plugins.py** - Remove Advanced-Alchemy plugin
3. **Migrate base service** - Ensure `_base.py` has all needed utilities
4. **Migrate services** - Start with simple services like `_tags.py`
5. **Update routes** - Migrate corresponding routes after each service
6. **Test each component** - Ensure functionality works after each migration
7. **Remove old dependencies** - Clean up pyproject.toml

## Testing Strategy

After each component migration:

1. Run type checking: `make type-check`
2. Run linting: `make lint`
3. Run specific tests for the component
4. Test API endpoints manually or with integration tests

## Rollback Plan

- Keep backup of current working code
- Migrate one service/route pair at a time
- Test thoroughly before moving to next component
- Use version control to track changes and enable easy rollback
