# SQLSpec Migration Guide: From Advanced-Alchemy to SQLSpec

## Table of Contents

1. [Introduction](#introduction)
2. [Prerequisites](#prerequisites)
3. [Understanding the Migration](#understanding-the-migration)
4. [Current State Assessment](#current-state-assessment)
5. [Phase 1: Foundation Fixes](#phase-1-foundation-fixes)
6. [Phase 2: Service Migration](#phase-2-service-migration)
7. [Phase 3: Dependency System Update](#phase-3-dependency-system-update)
8. [Phase 4: Route Migration](#phase-4-route-migration)
9. [Phase 5: Testing and Validation](#phase-5-testing-and-validation)
10. [Troubleshooting Guide](#troubleshooting-guide)
11. [Complete Examples](#complete-examples)

---

## Introduction

### What is this migration?

This guide walks you through migrating a Litestar web application from using **Advanced-Alchemy** (an ORM-based database layer) to **SQLSpec** (a SQL-first database layer).

### Why migrate?

- **Better Performance**: SQLSpec uses direct SQL queries instead of ORM abstractions
- **Simpler Code**: No complex ORM relationships or lazy loading issues
- **Type Safety**: Full TypeScript-style type checking for database operations
- **Maintainability**: Clearer, more explicit database operations

### What will change?

- Database queries will use SQL builders instead of ORM models
- Services will inherit from SQLSpec base classes
- Routes will use schema objects instead of ORM models
- Dependencies will be simpler and more explicit

### What stays the same?

- API endpoints remain unchanged
- Frontend continues to work without modifications
- Database schema stays the same
- Authentication and authorization unchanged

---

## Prerequisites

### Required Knowledge

- Basic Python programming
- Understanding of web APIs (GET, POST, PUT, DELETE)
- Basic SQL knowledge (SELECT, INSERT, UPDATE, DELETE)
- Command line usage

### Required Tools

Ensure you have these installed:

```bash
# Check Python version (need 3.11+)
python --version

# Check if uv is installed (Python package manager)
uv --version

# Check if git is installed
git --version

# Check if PostgreSQL is running (if using PostgreSQL)
pg_isready
```

### Project Setup

```bash
# Clone the repository if you haven't
git clone <your-repo-url>
cd litestar-sqlstack

# Create a virtual environment
uv venv

# Install dependencies
uv pip install -e .

# Verify installation
uv run litestar --version
```

---

## Understanding the Migration

### What is Advanced-Alchemy?

Advanced-Alchemy is an ORM (Object-Relational Mapping) library that:

- Maps database tables to Python classes
- Handles relationships automatically
- Provides lazy loading of related data
- Uses SQLAlchemy under the hood

Example of Advanced-Alchemy code:

```python
# ORM Model
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    teams = relationship("Team", back_populates="users")

# Service using ORM
class UserService(SQLAlchemyAsyncRepositoryService[User]):
    async def get_user_with_teams(self, user_id: int) -> User:
        return await self.repository.get_one(
            select(User).options(selectinload(User.teams))
            .where(User.id == user_id)
        )
```

### What is SQLSpec?

SQLSpec is a SQL-first database library that:

- Uses direct SQL queries with a builder pattern
- Converts results to type-safe schema objects
- No hidden queries or lazy loading
- Explicit and predictable behavior

Example of SQLSpec code:

```python
# Schema (not an ORM model)
class UserDto(BaseModel):
    id: int
    email: str

# Service using SQLSpec
class UserService(AsyncpgService[UserDto]):
    async def get_user(self, user_id: int) -> UserDto:
        stmt = sql.select().from_("users").where_eq(id=user_id)
        return await self.select_one(stmt, schema_type=UserDto)
```

### Key Differences

| Feature | Advanced-Alchemy | SQLSpec |
|---------|-----------------|---------|
| Query Style | ORM methods | SQL builders |
| Models | ORM classes | Pydantic schemas |
| Relationships | Automatic | Manual JOINs |
| Type Safety | Runtime | Compile-time |
| Performance | Good | Better |
| Complexity | Higher | Lower |

---

## Current State Assessment

### Step 1: Check Current Migration Status

Run this command to see which files still use Advanced-Alchemy:

```bash
# Find all Python files with Advanced-Alchemy imports
rg "from advanced_alchemy|from sqlalchemy" --type py

# Count how many files need migration
rg "from advanced_alchemy|from sqlalchemy" --type py | wc -l
```

### Step 2: Identify Migration Status

Check the migration status table:

```text
Component         | Status      | Files to Check
------------------|-------------|----------------
Configuration     | ✅ Complete | config.py
Base Service      | ❌ Broken   | services/_base.py
Services          | ⚠️ Partial  | services/*.py
Routes            | ❌ Pending  | server/routes/*.py
Dependencies      | ❌ Pending  | server/deps.py
```

### Step 3: List Services Status

Check each service file:

```bash
# List all service files
ls -la sqlstack/services/_*.py

# Check which services are migrated (don't have advanced_alchemy imports)
for file in sqlstack/services/_*.py; do
    echo -n "$file: "
    if grep -q "advanced_alchemy" "$file"; then
        echo "❌ Needs migration"
    else
        echo "✅ Already migrated"
    fi
done
```

Expected output:

```
sqlstack/services/_base.py: ✅ Already migrated
sqlstack/services/_teams.py: ✅ Already migrated
sqlstack/services/_users.py: ✅ Already migrated
sqlstack/services/_tags.py: ✅ Already migrated
sqlstack/services/_roles.py: ✅ Already migrated
sqlstack/services/_user_oauth_accounts.py: ❌ Needs migration
sqlstack/services/_user_roles.py: ❌ Needs migration
sqlstack/services/_team_files.py: ❌ Needs migration
sqlstack/services/_team_invitations.py: ❌ Needs migration
sqlstack/services/_team_members.py: ❌ Needs migration
```

---

## Phase 1: Foundation Fixes

This phase fixes critical issues that block all other work. **Must be completed first!**

### Step 1.1: Fix Base Service Imports

The base service is missing critical imports that all other services depend on.

#### Check the current _base.py file

```bash
# Look at the current imports
head -20 sqlstack/services/_base.py
```

#### What's wrong

The file is missing imports for `OffsetPagination` and `StatementFilter` that other services expect.

#### Fix the imports

Open `sqlstack/services/_base.py` in your editor and add these lines after the existing imports:

```python
# Find this section (around line 1-10)
from typing import TYPE_CHECKING, Generic, TypeVar

from sqlspec.adapters.asyncpg import AsyncpgDriver

# ADD THESE TWO LINES:
from sqlspec.service.pagination import OffsetPagination
from sqlstack.services._base import StatementFilter

# Then update the __all__ export (find this line)
__all__ = ("AsyncpgService",)

# CHANGE IT TO:
__all__ = ("AsyncpgService", "OffsetPagination", "StatementFilter")
```

#### Verify the fix

```bash
# Check if imports are correct
python -c "from sqlstack.services._base import AsyncpgService, OffsetPagination, StatementFilter; print('✅ Imports working!')"
```

Expected output: `✅ Imports working!`

### Step 1.2: Fix Import Paths Project-Wide

Many files incorrectly import from "app" instead of "sqlstack".

#### Find all incorrect imports

```bash
# List all files with wrong imports
rg "from app import|from app\." --type py
```

#### Fix using find and replace

##### Option A: Using sed (Linux/Mac)

```bash
# Create backup first
cp -r sqlstack sqlstack.backup

# Fix all Python files
find sqlstack -name "*.py" -type f -exec sed -i 's/from app import/from sqlstack import/g' {} \;
find sqlstack -name "*.py" -type f -exec sed -i 's/from app\./from sqlstack./g' {} \;
```

##### Option B: Using your IDE

1. Open your IDE's Find and Replace (usually Ctrl+Shift+H or Cmd+Shift+H)
2. Find: `from app import`
3. Replace: `from sqlstack import`
4. Scope: Entire project
5. File mask: `*.py`
6. Click "Replace All"
7. Repeat for `from app.` → `from sqlstack.`

#### Verify the fixes

```bash
# Should return nothing (no more "from app" imports)
rg "from app import|from app\." --type py

# Test that imports work
python -c "from sqlstack import schemas; print('✅ Import paths fixed!')"
```

### Step 1.3: Test Foundation Fixes

Run a basic test to ensure the foundation is solid:

```bash
# Test importing a migrated service
python -c "
from sqlstack.services._users import UserService
from sqlstack.services._teams import TeamService
print('✅ Foundation fixes complete! Services can be imported.')
"
```

---

## Phase 2: Service Migration

Now we'll migrate each remaining service from Advanced-Alchemy to SQLSpec.

### Understanding Service Migration

Each service needs these changes:

1. **Remove** Advanced-Alchemy imports
2. **Add** SQLSpec imports
3. **Remove** Repository class
4. **Convert** methods to use SQL builders
5. **Update** return types to schemas

### Step 2.1: Migrate User OAuth Accounts Service

This is the simplest service to migrate - good for learning the pattern.

#### Current file check

```bash
# View the current file
cat sqlstack/services/_user_oauth_accounts.py
```

#### Create the migrated version

Open `sqlstack/services/_user_oauth_accounts.py` and replace its entire contents:

```python
"""User OAuth Account Service."""
from typing import TYPE_CHECKING

from sqlspec import sql

from sqlstack import schemas as s
from sqlstack.services._base import AsyncpgService, OffsetPagination, StatementFilter

if TYPE_CHECKING:
    from uuid import UUID

__all__ = ["UserOAuthAccountService"]


class UserOAuthAccountService(AsyncpgService[s.UserOAuthAccountDto]):
    """Service for managing user OAuth accounts."""

    async def get_by_oauth_id(self, oauth_account_id: str) -> s.UserOAuthAccountDto:
        """Get OAuth account by OAuth provider ID.

        Args:
            oauth_account_id: The OAuth provider's user ID

        Returns:
            UserOAuthAccountDto: The OAuth account data

        Raises:
            NotFoundError: If account not found
        """
        stmt = (
            sql.select()
            .from_("user_oauth_accounts")
            .where_eq(oauth_account_id=oauth_account_id)
        )
        return await self.select_one(stmt, schema_type=s.UserOAuthAccountDto)

    async def get_by_user_id(self, user_id: UUID) -> list[s.UserOAuthAccountDto]:
        """Get all OAuth accounts for a user.

        Args:
            user_id: The user's ID

        Returns:
            List of OAuth accounts
        """
        stmt = (
            sql.select()
            .from_("user_oauth_accounts")
            .where_eq(user_id=user_id)
        )
        results = await self.driver.execute_many(stmt)
        return [self.to_schema(r, schema_type=s.UserOAuthAccountDto) for r in results]

    async def create(self, data: s.UserOAuthAccountCreate) -> s.UserOAuthAccountDto:
        """Create a new OAuth account.

        Args:
            data: OAuth account creation data

        Returns:
            UserOAuthAccountDto: Created OAuth account
        """
        stmt = (
            sql.insert("user_oauth_accounts")
            .values(**data.model_dump())
            .returning("*")
        )
        result = await self.driver.execute_returning(stmt)
        return self.to_schema(result[0], schema_type=s.UserOAuthAccountDto)

    async def delete_by_oauth_id(self, oauth_account_id: str) -> None:
        """Delete OAuth account by OAuth provider ID.

        Args:
            oauth_account_id: The OAuth provider's user ID
        """
        stmt = (
            sql.delete("user_oauth_accounts")
            .where_eq(oauth_account_id=oauth_account_id)
        )
        await self.driver.execute(stmt)

    async def list(
        self,
        filters: list[StatementFilter] | None = None
    ) -> OffsetPagination[s.UserOAuthAccountDto]:
        """List OAuth accounts with pagination.

        Args:
            filters: Optional filters to apply

        Returns:
            Paginated list of OAuth accounts
        """
        return await self.paginate(
            "user_oauth_accounts",
            filters=filters,
            schema_type=s.UserOAuthAccountDto,
        )
```

#### Test the migrated service

```python
# Save this as test_oauth_service.py
from sqlstack.services._user_oauth_accounts import UserOAuthAccountService

# If no errors, the service is properly migrated
print("✅ UserOAuthAccountService migrated successfully!")

# Check that all methods are available
service = UserOAuthAccountService(None)  # None is OK for testing imports
print("Available methods:", [m for m in dir(service) if not m.startswith("_")])
```

Run it:

```bash
python test_oauth_service.py
```

### Step 2.2: Migrate User Roles Service

This is a junction table service (many-to-many relationship).

#### View current file

```bash
cat sqlstack/services/_user_roles.py
```

#### Create the migrated version

Replace the entire contents of `sqlstack/services/_user_roles.py`:

```python
"""User Role Service."""
from typing import TYPE_CHECKING

from sqlspec import sql

from sqlstack import schemas as s
from sqlstack.services._base import AsyncpgService, OffsetPagination, StatementFilter

if TYPE_CHECKING:
    from uuid import UUID

__all__ = ["UserRoleService"]


class UserRoleService(AsyncpgService[s.UserRoleDto]):
    """Service for managing user-role assignments."""

    async def assign_role_to_user(
        self,
        user_id: UUID,
        role_id: UUID
    ) -> s.UserRoleDto:
        """Assign a role to a user.

        Args:
            user_id: The user's ID
            role_id: The role's ID

        Returns:
            UserRoleDto: The created assignment
        """
        stmt = (
            sql.insert("user_roles")
            .values(user_id=user_id, role_id=role_id)
            .returning("*")
        )
        result = await self.driver.execute_returning(stmt)
        return self.to_schema(result[0], schema_type=s.UserRoleDto)

    async def remove_role_from_user(
        self,
        user_id: UUID,
        role_id: UUID
    ) -> None:
        """Remove a role from a user.

        Args:
            user_id: The user's ID
            role_id: The role's ID
        """
        stmt = (
            sql.delete("user_roles")
            .where_eq(user_id=user_id, role_id=role_id)
        )
        await self.driver.execute(stmt)

    async def get_user_roles(self, user_id: UUID) -> list[s.RoleDto]:
        """Get all roles for a user.

        Args:
            user_id: The user's ID

        Returns:
            List of roles assigned to the user
        """
        stmt = (
            sql.select("r.*")
            .from_("roles r")
            .join("user_roles ur", "r.id = ur.role_id")
            .where_eq(**{"ur.user_id": user_id})
        )
        results = await self.driver.execute_many(stmt)
        return [self.to_schema(r, schema_type=s.RoleDto) for r in results]

    async def get_role_users(self, role_id: UUID) -> list[s.UserDto]:
        """Get all users with a specific role.

        Args:
            role_id: The role's ID

        Returns:
            List of users with this role
        """
        stmt = (
            sql.select("u.*")
            .from_("users u")
            .join("user_roles ur", "u.id = ur.user_id")
            .where_eq(**{"ur.role_id": role_id})
        )
        results = await self.driver.execute_many(stmt)
        return [self.to_schema(r, schema_type=s.UserDto) for r in results]

    async def user_has_role(
        self,
        user_id: UUID,
        role_id: UUID
    ) -> bool:
        """Check if a user has a specific role.

        Args:
            user_id: The user's ID
            role_id: The role's ID

        Returns:
            True if user has the role
        """
        stmt = (
            sql.select("1")
            .from_("user_roles")
            .where_eq(user_id=user_id, role_id=role_id)
            .limit(1)
        )
        result = await self.driver.execute_one_or_none(stmt)
        return result is not None

    async def list_and_count(
        self,
        filters: list[StatementFilter] | None = None
    ) -> OffsetPagination[s.UserRoleDto]:
        """List user-role assignments with pagination.

        Args:
            filters: Optional filters to apply

        Returns:
            Paginated list of assignments
        """
        return await self.paginate(
            "user_roles",
            filters=filters,
            schema_type=s.UserRoleDto,
        )
```

### Step 2.3: Continue with Remaining Services

Follow the same pattern for the remaining services. Here's a checklist:

- [ ] `_team_files.py` - File management service
- [ ] `_team_invitations.py` - Invitation service with expiration
- [ ] `_team_members.py` - Complex service with multiple relationships

For each service:

1. **Open the file** and study the current methods
2. **Copy a migrated service** as a template (like `_users.py`)
3. **Convert each method** to use SQL builders
4. **Test the imports** after migration

### Common Migration Patterns

#### Pattern 1: Basic CRUD

```python
# CREATE
async def create(self, data: s.SchemaCreate) -> s.Schema:
    stmt = sql.insert("table_name").values(**data.model_dump()).returning("*")
    result = await self.driver.execute_returning(stmt)
    return self.to_schema(result[0], schema_type=s.Schema)

# READ
async def get(self, item_id: UUID) -> s.Schema:
    stmt = sql.select().from_("table_name").where_eq(id=item_id)
    return await self.select_one(stmt, schema_type=s.Schema)

# UPDATE
async def update(self, item_id: UUID, data: s.SchemaUpdate) -> s.Schema:
    values = data.model_dump(exclude_unset=True)
    stmt = sql.update("table_name").set(**values).where_eq(id=item_id).returning("*")
    result = await self.driver.execute_returning(stmt)
    return self.to_schema(result[0], schema_type=s.Schema)

# DELETE
async def delete(self, item_id: UUID) -> None:
    stmt = sql.delete("table_name").where_eq(id=item_id)
    await self.driver.execute(stmt)
```

#### Pattern 2: Queries with JOINs

```python
async def get_with_related(self, item_id: UUID) -> s.SchemaWithRelated:
    stmt = (
        sql.select("t.*", "r.name as related_name")
        .from_("table t")
        .join("related r", "t.related_id = r.id")
        .where_eq(**{"t.id": item_id})
    )
    result = await self.driver.execute_one(stmt)
    return self.to_schema(result, schema_type=s.SchemaWithRelated)
```

#### Pattern 3: Filtering and Search

```python
async def search(self, search_term: str) -> list[s.Schema]:
    stmt = (
        sql.select()
        .from_("table_name")
        .where(sql.or_(
            sql.condition("name ILIKE :search"),
            sql.condition("description ILIKE :search")
        ))
    )
    results = await self.driver.execute_many(stmt, search=f"%{search_term}%")
    return [self.to_schema(r, schema_type=s.Schema) for r in results]
```

---

## Phase 3: Dependency System Update

This phase updates how dependencies are injected into routes.

### Step 3.1: Understand the Current System

Advanced-Alchemy uses complex dependency creation:

```python
# OLD WAY - Don't use this
dependencies = create_service_dependencies(
    TeamService,
    key="teams_service",
    load=[m.Team.tags, m.Team.members],  # ORM relationship loading
)
```

SQLSpec uses simple dependency injection:

```python
# NEW WAY - Use this
dependencies = {
    "team_service": Provide(TeamService.new),
}
```

### Step 3.2: Update deps.py

Open `sqlstack/server/deps.py` and make these changes:

#### Remove these imports

```python
# DELETE THESE LINES
from advanced_alchemy.extensions.litestar import (
    create_service_dependencies,
    provide_limit_offset_pagination,
)
from sqlalchemy.orm import selectinload, joinedload, noload
```

#### Add these imports

```python
# ADD THESE LINES
from litestar.di import Provide
from sqlspec.extensions.litestar.providers import create_filter_dependencies, FilterConfig
from sqlspec.adapters.asyncpg import AsyncpgDriver
from sqlstack.services._base import LimitOffsetFilter

# Import all services
from sqlstack.services import (
    UserService,
    TeamService,
    RoleService,
    TagService,
    UserOAuthAccountService,
    UserRoleService,
    TeamFileService,
    TeamInvitationService,
    TeamMemberService,
)
```

#### Add service factory functions

```python
# Simple service factories
async def provide_user_service(db_session: AsyncpgDriver) -> UserService:
    """Provide user service instance."""
    return UserService(db_session)

async def provide_team_service(db_session: AsyncpgDriver) -> TeamService:
    """Provide team service instance."""
    return TeamService(db_session)

async def provide_role_service(db_session: AsyncpgDriver) -> RoleService:
    """Provide role service instance."""
    return RoleService(db_session)

# Add similar functions for all services...
```

#### Add filter configurations

```python
# Pre-configured filter dependencies for common use cases
USER_FILTER_CONFIG: FilterConfig = {
    "id_filter": UUID,
    "pagination_type": "limit_offset",
    "pagination_size": 20,
    "search": ["email", "name"],
    "created_at": True,
    "updated_at": True,
}

TEAM_FILTER_CONFIG: FilterConfig = {
    "id_filter": UUID,
    "pagination_type": "limit_offset",
    "pagination_size": 20,
    "search": ["name", "description"],
    "sort_field": "name",
    "sort_order": "asc",
    "created_at": True,
    "updated_at": True,
}

# Create filter dependencies
USER_FILTERS = create_filter_dependencies(USER_FILTER_CONFIG)
TEAM_FILTERS = create_filter_dependencies(TEAM_FILTER_CONFIG)
```

### Step 3.3: Understanding Filter Dependencies

SQLSpec's `create_filter_dependencies` automatically creates these dependencies:

| Filter Type | Query Parameter | Example URL |
|------------|-----------------|-------------|
| ID Filter | `?ids=uuid1,uuid2` | `/api/users?ids=123,456` |
| Pagination | `?currentPage=1&pageSize=20` | `/api/users?currentPage=2&pageSize=10` |
| Search | `?searchString=john` | `/api/users?searchString=john` |
| Sorting | `?orderBy=name&sortOrder=asc` | `/api/users?orderBy=created_at&sortOrder=desc` |
| Date Range | `?createdAfter=2024-01-01` | `/api/users?createdAfter=2024-01-01&createdBefore=2024-12-31` |

---

## Phase 4: Route Migration

Now we'll migrate routes to use the new services and dependencies.

### Step 4.1: Understanding Route Changes

Routes need these updates:

1. Remove Advanced-Alchemy imports
2. Remove ORM model references
3. Update dependency injection
4. Use schema objects for responses

### Step 4.2: Migrate a Simple Route (roles.py)

Let's start with a simple route file.

#### View the current file

```bash
cat sqlstack/server/routes/roles.py
```

#### Create the migrated version

Replace the entire contents of `sqlstack/server/routes/roles.py`:

```python
"""Role management routes."""
from typing import TYPE_CHECKING
from uuid import UUID

from litestar import Controller, delete, get, patch, post
from litestar.di import Provide
from litestar.params import Parameter

from sqlstack import schemas as s
from sqlstack.server.deps import provide_role_service
from sqlstack.services import RoleService, OffsetPagination

if TYPE_CHECKING:
    from sqlspec.extensions.litestar.providers import FilterTypes

__all__ = ["RoleController"]


class RoleController(Controller):
    """Role management endpoints."""

    path = "/api/roles"
    tags = ["Roles"]
    dependencies = {
        "role_service": Provide(provide_role_service),
    }

    @get()
    async def list_roles(
        self,
        role_service: RoleService,
        limit: int = Parameter(default=20, ge=1, le=100),
        offset: int = Parameter(default=0, ge=0),
    ) -> OffsetPagination[s.RoleDto]:
        """List all roles with pagination.

        Args:
            role_service: Injected role service
            limit: Number of items per page
            offset: Number of items to skip

        Returns:
            Paginated list of roles
        """
        from sqlstack.services._base import LimitOffsetFilter

        filters = [LimitOffsetFilter(limit=limit, offset=offset)]
        return await role_service.list(filters=filters)

    @get("/{role_id:uuid}")
    async def get_role(
        self,
        role_service: RoleService,
        role_id: UUID,
    ) -> s.RoleDto:
        """Get a role by ID.

        Args:
            role_service: Injected role service
            role_id: Role ID

        Returns:
            Role details
        """
        return await role_service.get(role_id)

    @post()
    async def create_role(
        self,
        role_service: RoleService,
        data: s.RoleCreate,
    ) -> s.RoleDto:
        """Create a new role.

        Args:
            role_service: Injected role service
            data: Role creation data

        Returns:
            Created role
        """
        return await role_service.create(data)

    @patch("/{role_id:uuid}")
    async def update_role(
        self,
        role_service: RoleService,
        role_id: UUID,
        data: s.RoleUpdate,
    ) -> s.RoleDto:
        """Update a role.

        Args:
            role_service: Injected role service
            role_id: Role ID
            data: Role update data

        Returns:
            Updated role
        """
        return await role_service.update(role_id, data)

    @delete("/{role_id:uuid}")
    async def delete_role(
        self,
        role_service: RoleService,
        role_id: UUID,
    ) -> None:
        """Delete a role.

        Args:
            role_service: Injected role service
            role_id: Role ID
        """
        await role_service.delete(role_id)
```

### Step 4.3: Migrate a Complex Route with Filters

Let's migrate a route that uses full filter dependencies.

Replace the contents of `sqlstack/server/routes/user.py`:

```python
"""User management routes."""
from typing import TYPE_CHECKING
from uuid import UUID

from litestar import Controller, delete, get, patch, post
from litestar.di import Provide

from sqlspec.extensions.litestar.providers import create_filter_dependencies, FilterConfig
from sqlstack import schemas as s
from sqlstack.server.deps import provide_user_service
from sqlstack.services import UserService
from sqlstack.services._base import OffsetPagination

if TYPE_CHECKING:
    from sqlspec.extensions.litestar.providers import FilterTypes

__all__ = ["UserController"]

# Configure filters for users
USER_FILTERS: FilterConfig = {
    "id_filter": UUID,
    "pagination_type": "limit_offset",
    "pagination_size": 20,
    "search": ["email", "name"],
    "sort_field": "created_at",
    "sort_order": "desc",
    "created_at": True,
    "updated_at": True,
}


class UserController(Controller):
    """User management endpoints."""

    path = "/api/users"
    tags = ["Users"]
    dependencies = {
        "user_service": Provide(provide_user_service),
        **create_filter_dependencies(USER_FILTERS),
    }

    @get()
    async def list_users(
        self,
        user_service: UserService,
        filters: list[FilterTypes],
    ) -> OffsetPagination[s.UserDto]:
        """List users with filtering, pagination, and search.

        Query parameters:
        - currentPage: Page number (default: 1)
        - pageSize: Items per page (default: 20)
        - searchString: Search in email and name
        - orderBy: Sort field (default: created_at)
        - sortOrder: asc or desc (default: desc)
        - createdAfter: Filter by creation date
        - createdBefore: Filter by creation date
        - ids: Comma-separated list of IDs

        Args:
            user_service: Injected user service
            filters: Automatically injected filters based on query params

        Returns:
            Paginated list of users
        """
        return await user_service.list(filters=filters)

    @get("/{user_id:uuid}")
    async def get_user(
        self,
        user_service: UserService,
        user_id: UUID,
    ) -> s.UserDto:
        """Get a user by ID.

        Args:
            user_service: Injected user service
            user_id: User ID

        Returns:
            User details
        """
        return await user_service.get(user_id)

    @get("/{user_id:uuid}/roles")
    async def get_user_roles(
        self,
        user_service: UserService,
        user_id: UUID,
    ) -> list[s.RoleDto]:
        """Get roles assigned to a user.

        Args:
            user_service: Injected user service
            user_id: User ID

        Returns:
            List of roles
        """
        # This would typically use UserRoleService
        # For now, showing the pattern
        return await user_service.get_user_roles(user_id)

    @post()
    async def create_user(
        self,
        user_service: UserService,
        data: s.UserCreate,
    ) -> s.UserDto:
        """Create a new user.

        Args:
            user_service: Injected user service
            data: User creation data

        Returns:
            Created user
        """
        return await user_service.create(data)

    @patch("/{user_id:uuid}")
    async def update_user(
        self,
        user_service: UserService,
        user_id: UUID,
        data: s.UserUpdate,
    ) -> s.UserDto:
        """Update a user.

        Args:
            user_service: Injected user service
            user_id: User ID
            data: User update data

        Returns:
            Updated user
        """
        return await user_service.update(user_id, data)

    @delete("/{user_id:uuid}")
    async def delete_user(
        self,
        user_service: UserService,
        user_id: UUID,
    ) -> None:
        """Delete a user.

        Args:
            user_service: Injected user service
            user_id: User ID
        """
        await user_service.delete(user_id)
```

### Step 4.4: Test the Migrated Routes

After migrating a route, test it:

```bash
# Start the development server
uv run litestar run --reload

# In another terminal, test the endpoints

# Test listing with pagination
curl "http://localhost:8000/api/users?currentPage=1&pageSize=10"

# Test search
curl "http://localhost:8000/api/users?searchString=john"

# Test sorting
curl "http://localhost:8000/api/users?orderBy=email&sortOrder=asc"

# Test getting a specific user (replace with actual UUID)
curl "http://localhost:8000/api/users/123e4567-e89b-12d3-a456-426614174000"
```

### Common Route Migration Issues

#### Issue 1: Missing imports

```python
# If you see: ImportError: cannot import name 'FilterTypes'
# Add this import:
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from sqlspec.extensions.litestar.providers import FilterTypes
```

#### Issue 2: Response format

```python
# Make sure responses use schema objects, not ORM models
# Wrong:
return user  # ORM model

# Right:
return s.UserDto.from_orm(user)  # Schema object
```

#### Issue 3: Guards and permissions

```python
# If you have guards that expect ORM models, update them:
# Old:
@requires_team_membership(load=[m.Team.members])

# New:
@requires_team_membership  # Simplified, service handles loading
```

---

## Phase 5: Testing and Validation

### Step 5.1: Run Type Checking

```bash
# Run mypy type checking
uv run mypy sqlstack

# Run pyright type checking
uv run pyright sqlstack

# If you see errors, fix them before proceeding
```

### Step 5.2: Run Linting

```bash
# Run linting
uv run ruff check sqlstack

# Auto-fix linting issues
uv run ruff check --fix sqlstack

# Format code
uv run ruff format sqlstack
```

### Step 5.3: Run Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_services.py -v

# Run with coverage
uv run pytest --cov=sqlstack --cov-report=html
```

### Step 5.4: Manual API Testing

Create a test script `test_api.py`:

```python
import httpx
import asyncio

async def test_api():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Test user listing
        response = await client.get("/api/users")
        print(f"Users list: {response.status_code}")
        print(f"Response: {response.json()}")

        # Test pagination
        response = await client.get("/api/users?currentPage=1&pageSize=5")
        print(f"Paginated users: {response.status_code}")

        # Test search
        response = await client.get("/api/users?searchString=admin")
        print(f"Search results: {response.status_code}")

# Run the tests
asyncio.run(test_api())
```

### Step 5.5: Check for Remaining Advanced-Alchemy Imports

```bash
# Final check - should return nothing
rg "from advanced_alchemy|from sqlalchemy" --type py sqlstack/

# If found, investigate and fix
```

### Step 5.6: Update Dependencies

Remove Advanced-Alchemy from `pyproject.toml`:

```toml
# Find and remove this line:
advanced-alchemy = "^x.x.x"

# Then update lock file:
uv lock
```

---

## Troubleshooting Guide

### Common Errors and Solutions

#### Error: "ImportError: cannot import name 'OffsetPagination'"

**Cause**: Base service imports not fixed
**Solution**: Complete Phase 1, Step 1.1

#### Error: "AttributeError: 'NoneType' object has no attribute 'execute'"

**Cause**: Service not properly initialized with database driver
**Solution**: Ensure service is created with driver instance:

```python
# Wrong:
service = UserService(None)

# Right:
service = UserService(db_session)  # db_session is AsyncpgDriver instance
```

#### Error: "TypeError: 'FilterTypes' is not defined"

**Cause**: Missing TYPE_CHECKING import
**Solution**: Add proper imports:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from sqlspec.extensions.litestar.providers import FilterTypes
```

#### Error: "sqlspec.exceptions.NotFoundError"

**Cause**: Query returned no results
**Solution**: This is expected behavior. Handle in route:

```python
from litestar.exceptions import HTTPException

try:
    user = await user_service.get(user_id)
except NotFoundError:
    raise HTTPException(status_code=404, detail="User not found")
```

#### Error: "ValueError: too many values to unpack"

**Cause**: SQL query returning wrong columns
**Solution**: Check your SELECT statement:

```python
# Wrong:
stmt = sql.select("*")  # Might return extra columns

# Right:
stmt = sql.select().from_("table")  # Returns all columns properly
# Or be specific:
stmt = sql.select("id", "name", "email").from_("users")
```

### Performance Issues

#### Slow Queries

Check for missing indexes:

```sql
-- Check query plan
EXPLAIN ANALYZE
SELECT * FROM users WHERE email = 'test@example.com';

-- Add index if needed
CREATE INDEX idx_users_email ON users(email);
```

#### N+1 Queries

SQLSpec doesn't have automatic relationship loading, so be explicit:

```python
# Instead of multiple queries:
for team in teams:
    members = await get_team_members(team.id)  # N queries!

# Use a single query with JOIN:
stmt = (
    sql.select("t.*", "array_agg(m.user_id) as member_ids")
    .from_("teams t")
    .join("team_members m", "t.id = m.team_id", how="left")
    .group_by("t.id")
)
```

---

## Complete Examples

### Example 1: Complete Service Migration

Here's a fully migrated service with all common patterns:

```python
"""Example: Complete team service migration."""
from typing import TYPE_CHECKING
from uuid import UUID

from sqlspec import sql
from sqlstack import schemas as s
from sqlstack.services._base import AsyncpgService, OffsetPagination, StatementFilter

if TYPE_CHECKING:
    from datetime import datetime

__all__ = ["TeamService"]


class TeamService(AsyncpgService[s.TeamDto]):
    """Service for managing teams."""

    # Basic CRUD operations

    async def create(self, data: s.TeamCreate) -> s.TeamDto:
        """Create a new team."""
        stmt = (
            sql.insert("teams")
            .values(**data.model_dump())
            .returning("*")
        )
        result = await self.driver.execute_returning(stmt)
        return self.to_schema(result[0], schema_type=s.TeamDto)

    async def get(self, team_id: UUID) -> s.TeamDto:
        """Get team by ID."""
        stmt = sql.select().from_("teams").where_eq(id=team_id)
        return await self.select_one(stmt, schema_type=s.TeamDto)

    async def update(self, team_id: UUID, data: s.TeamUpdate) -> s.TeamDto:
        """Update team."""
        values = data.model_dump(exclude_unset=True)
        stmt = (
            sql.update("teams")
            .set(**values)
            .where_eq(id=team_id)
            .returning("*")
        )
        result = await self.driver.execute_returning(stmt)
        return self.to_schema(result[0], schema_type=s.TeamDto)

    async def delete(self, team_id: UUID) -> None:
        """Delete team."""
        stmt = sql.delete("teams").where_eq(id=team_id)
        await self.driver.execute(stmt)

    # Complex queries

    async def get_with_members(self, team_id: UUID) -> s.TeamWithMembersDto:
        """Get team with member details."""
        # Main team query
        team_stmt = sql.select().from_("teams").where_eq(id=team_id)
        team = await self.select_one(team_stmt, schema_type=s.TeamDto)

        # Get members
        members_stmt = (
            sql.select("u.*", "tm.role")
            .from_("users u")
            .join("team_members tm", "u.id = tm.user_id")
            .where_eq(**{"tm.team_id": team_id})
        )
        members = await self.driver.execute_many(members_stmt)

        # Combine results
        return s.TeamWithMembersDto(
            **team.model_dump(),
            members=[
                s.TeamMemberDto(
                    **self.to_schema(m, schema_type=s.UserDto).model_dump(),
                    role=m["role"]
                )
                for m in members
            ]
        )

    async def search(
        self,
        search_term: str,
        include_archived: bool = False
    ) -> list[s.TeamDto]:
        """Search teams by name or description."""
        conditions = [
            sql.or_(
                sql.condition("name ILIKE :search"),
                sql.condition("description ILIKE :search")
            )
        ]

        if not include_archived:
            conditions.append(sql.condition("archived_at IS NULL"))

        stmt = (
            sql.select()
            .from_("teams")
            .where(*conditions)
            .order_by("name")
        )

        results = await self.driver.execute_many(
            stmt,
            search=f"%{search_term}%"
        )
        return [self.to_schema(r, schema_type=s.TeamDto) for r in results]

    async def get_by_slug(self, slug: str) -> s.TeamDto:
        """Get team by URL slug."""
        stmt = sql.select().from_("teams").where_eq(slug=slug)
        return await self.select_one(stmt, schema_type=s.TeamDto)

    async def add_member(
        self,
        team_id: UUID,
        user_id: UUID,
        role: str = "member"
    ) -> s.TeamMemberDto:
        """Add a member to team."""
        stmt = (
            sql.insert("team_members")
            .values(team_id=team_id, user_id=user_id, role=role)
            .returning("*")
        )
        result = await self.driver.execute_returning(stmt)
        return self.to_schema(result[0], schema_type=s.TeamMemberDto)

    async def remove_member(self, team_id: UUID, user_id: UUID) -> None:
        """Remove a member from team."""
        stmt = (
            sql.delete("team_members")
            .where_eq(team_id=team_id, user_id=user_id)
        )
        await self.driver.execute(stmt)

    async def get_user_teams(self, user_id: UUID) -> list[s.TeamDto]:
        """Get all teams a user belongs to."""
        stmt = (
            sql.select("t.*")
            .from_("teams t")
            .join("team_members tm", "t.id = tm.team_id")
            .where_eq(**{"tm.user_id": user_id})
            .order_by("t.name")
        )
        results = await self.driver.execute_many(stmt)
        return [self.to_schema(r, schema_type=s.TeamDto) for r in results]

    # Pagination with filters

    async def list(
        self,
        filters: list[StatementFilter] | None = None
    ) -> OffsetPagination[s.TeamDto]:
        """List teams with pagination and filtering."""
        return await self.paginate(
            "teams",
            filters=filters,
            schema_type=s.TeamDto,
        )

    # Business logic

    async def archive(self, team_id: UUID) -> s.TeamDto:
        """Archive a team (soft delete)."""
        stmt = (
            sql.update("teams")
            .set(archived_at=sql.func.now())
            .where_eq(id=team_id)
            .returning("*")
        )
        result = await self.driver.execute_returning(stmt)
        return self.to_schema(result[0], schema_type=s.TeamDto)

    async def unarchive(self, team_id: UUID) -> s.TeamDto:
        """Unarchive a team."""
        stmt = (
            sql.update("teams")
            .set(archived_at=None)
            .where_eq(id=team_id)
            .returning("*")
        )
        result = await self.driver.execute_returning(stmt)
        return self.to_schema(result[0], schema_type=s.TeamDto)

    async def transfer_ownership(
        self,
        team_id: UUID,
        new_owner_id: UUID
    ) -> s.TeamDto:
        """Transfer team ownership."""
        # Update team owner
        stmt = (
            sql.update("teams")
            .set(owner_id=new_owner_id)
            .where_eq(id=team_id)
            .returning("*")
        )
        result = await self.driver.execute_returning(stmt)

        # Update member role to owner
        await self.driver.execute(
            sql.update("team_members")
            .set(role="owner")
            .where_eq(team_id=team_id, user_id=new_owner_id)
        )

        return self.to_schema(result[0], schema_type=s.TeamDto)

    # Statistics and aggregations

    async def get_member_count(self, team_id: UUID) -> int:
        """Get number of members in a team."""
        stmt = (
            sql.select("COUNT(*)")
            .from_("team_members")
            .where_eq(team_id=team_id)
        )
        result = await self.driver.execute_one(stmt)
        return result[0]

    async def get_team_stats(self, team_id: UUID) -> s.TeamStatsDto:
        """Get team statistics."""
        stats_stmt = sql.text("""
            SELECT
                t.id,
                t.name,
                COUNT(DISTINCT tm.user_id) as member_count,
                COUNT(DISTINCT tf.id) as file_count,
                COALESCE(SUM(tf.size_bytes), 0) as total_storage_bytes,
                MAX(tm.created_at) as last_member_joined
            FROM teams t
            LEFT JOIN team_members tm ON t.id = tm.team_id
            LEFT JOIN team_files tf ON t.id = tf.team_id
            WHERE t.id = :team_id
            GROUP BY t.id, t.name
        """)

        result = await self.driver.execute_one(stats_stmt, team_id=team_id)
        return self.to_schema(result, schema_type=s.TeamStatsDto)
```

### Example 2: Complete Route Migration

Here's a fully migrated route controller with all features:

```python
"""Example: Complete team route controller."""
from typing import TYPE_CHECKING
from uuid import UUID

from litestar import Controller, delete, get, patch, post, Request
from litestar.di import Provide
from litestar.exceptions import HTTPException
from litestar.guards import requires_authentication

from sqlspec.extensions.litestar.providers import create_filter_dependencies, FilterConfig
from sqlstack import schemas as s
from sqlstack.server.deps import provide_team_service, provide_team_member_service
from sqlstack.services import TeamService, TeamMemberService
from sqlstack.services._base import OffsetPagination

if TYPE_CHECKING:
    from sqlspec.extensions.litestar.providers import FilterTypes

__all__ = ["TeamController"]

# Configure filters for teams
TEAM_FILTERS: FilterConfig = {
    "id_filter": UUID,
    "pagination_type": "limit_offset",
    "pagination_size": 20,
    "search": ["name", "description"],
    "sort_field": "created_at",
    "sort_order": "desc",
    "created_at": True,
    "updated_at": True,
    "in_fields": [{"name": "owner_id", "type_hint": UUID}],
}


class TeamController(Controller):
    """Team management endpoints."""

    path = "/api/teams"
    tags = ["Teams"]
    guards = [requires_authentication]
    dependencies = {
        "team_service": Provide(provide_team_service),
        "member_service": Provide(provide_team_member_service),
        **create_filter_dependencies(TEAM_FILTERS),
    }

    @get()
    async def list_teams(
        self,
        request: Request,
        team_service: TeamService,
        filters: list[FilterTypes],
    ) -> OffsetPagination[s.TeamDto]:
        """List teams with filtering and pagination.

        Query parameters:
        - currentPage: Page number (default: 1)
        - pageSize: Items per page (default: 20)
        - searchString: Search in name and description
        - orderBy: Sort field (default: created_at)
        - sortOrder: asc or desc (default: desc)
        - createdAfter: Filter by creation date
        - createdBefore: Filter by creation date
        - ownerIdIn: Filter by owner IDs
        - ids: Comma-separated list of team IDs

        Returns:
            Paginated list of teams
        """
        # Add user-specific filtering if needed
        user = request.user
        if not user.is_superuser:
            # Only show teams the user is a member of
            user_teams = await team_service.get_user_teams(user.id)
            team_ids = [t.id for t in user_teams]
            # Add custom filter logic here

        return await team_service.list(filters=filters)

    @get("/my")
    async def list_my_teams(
        self,
        request: Request,
        team_service: TeamService,
    ) -> list[s.TeamDto]:
        """List teams the current user belongs to.

        Returns:
            List of user's teams
        """
        user = request.user
        return await team_service.get_user_teams(user.id)

    @get("/{team_id:uuid}")
    async def get_team(
        self,
        team_service: TeamService,
        team_id: UUID,
    ) -> s.TeamDto:
        """Get team details.

        Args:
            team_id: Team ID

        Returns:
            Team details
        """
        return await team_service.get(team_id)

    @get("/{team_id:uuid}/full")
    async def get_team_with_members(
        self,
        request: Request,
        team_service: TeamService,
        team_id: UUID,
    ) -> s.TeamWithMembersDto:
        """Get team with all member details.

        Args:
            team_id: Team ID

        Returns:
            Team with members
        """
        # Check permissions
        user = request.user
        is_member = await team_service.is_member(team_id, user.id)
        if not is_member and not user.is_superuser:
            raise HTTPException(
                status_code=403,
                detail="You must be a team member to view details"
            )

        return await team_service.get_with_members(team_id)

    @post()
    async def create_team(
        self,
        request: Request,
        team_service: TeamService,
        data: s.TeamCreate,
    ) -> s.TeamDto:
        """Create a new team.

        The creating user becomes the team owner.

        Args:
            data: Team creation data

        Returns:
            Created team
        """
        user = request.user

        # Add owner_id to creation data
        create_data = data.model_dump()
        create_data["owner_id"] = user.id

        # Create team
        team = await team_service.create(s.TeamCreate(**create_data))

        # Add creator as owner member
        await team_service.add_member(team.id, user.id, role="owner")

        return team

    @patch("/{team_id:uuid}")
    async def update_team(
        self,
        request: Request,
        team_service: TeamService,
        team_id: UUID,
        data: s.TeamUpdate,
    ) -> s.TeamDto:
        """Update team details.

        Only team owners can update team details.

        Args:
            team_id: Team ID
            data: Team update data

        Returns:
            Updated team
        """
        user = request.user

        # Check if user is team owner
        team = await team_service.get(team_id)
        if team.owner_id != user.id and not user.is_superuser:
            raise HTTPException(
                status_code=403,
                detail="Only team owners can update team details"
            )

        return await team_service.update(team_id, data)

    @delete("/{team_id:uuid}")
    async def delete_team(
        self,
        request: Request,
        team_service: TeamService,
        team_id: UUID,
    ) -> None:
        """Delete a team.

        Only team owners can delete teams.

        Args:
            team_id: Team ID
        """
        user = request.user

        # Check if user is team owner
        team = await team_service.get(team_id)
        if team.owner_id != user.id and not user.is_superuser:
            raise HTTPException(
                status_code=403,
                detail="Only team owners can delete teams"
            )

        await team_service.delete(team_id)

    @post("/{team_id:uuid}/archive")
    async def archive_team(
        self,
        request: Request,
        team_service: TeamService,
        team_id: UUID,
    ) -> s.TeamDto:
        """Archive a team (soft delete).

        Args:
            team_id: Team ID

        Returns:
            Archived team
        """
        user = request.user

        # Check permissions
        team = await team_service.get(team_id)
        if team.owner_id != user.id and not user.is_superuser:
            raise HTTPException(
                status_code=403,
                detail="Only team owners can archive teams"
            )

        return await team_service.archive(team_id)

    # Member management endpoints

    @get("/{team_id:uuid}/members")
    async def list_team_members(
        self,
        team_service: TeamService,
        member_service: TeamMemberService,
        team_id: UUID,
    ) -> list[s.TeamMemberDto]:
        """List team members.

        Args:
            team_id: Team ID

        Returns:
            List of team members
        """
        return await member_service.get_team_members(team_id)

    @post("/{team_id:uuid}/members")
    async def add_team_member(
        self,
        request: Request,
        team_service: TeamService,
        team_id: UUID,
        data: s.TeamMemberAdd,
    ) -> s.TeamMemberDto:
        """Add a member to the team.

        Only team owners can add members.

        Args:
            team_id: Team ID
            data: Member addition data

        Returns:
            Added team member
        """
        user = request.user

        # Check if user is team owner
        team = await team_service.get(team_id)
        if team.owner_id != user.id and not user.is_superuser:
            raise HTTPException(
                status_code=403,
                detail="Only team owners can add members"
            )

        return await team_service.add_member(
            team_id,
            data.user_id,
            data.role or "member"
        )

    @delete("/{team_id:uuid}/members/{user_id:uuid}")
    async def remove_team_member(
        self,
        request: Request,
        team_service: TeamService,
        team_id: UUID,
        user_id: UUID,
    ) -> None:
        """Remove a member from the team.

        Team owners can remove any member.
        Members can remove themselves.

        Args:
            team_id: Team ID
            user_id: User ID to remove
        """
        current_user = request.user

        # Check permissions
        team = await team_service.get(team_id)
        is_owner = team.owner_id == current_user.id
        is_self = user_id == current_user.id

        if not (is_owner or is_self or current_user.is_superuser):
            raise HTTPException(
                status_code=403,
                detail="You can only remove yourself or be a team owner"
            )

        # Don't allow removing the owner
        if user_id == team.owner_id:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove team owner. Transfer ownership first."
            )

        await team_service.remove_member(team_id, user_id)

    @post("/{team_id:uuid}/transfer-ownership")
    async def transfer_ownership(
        self,
        request: Request,
        team_service: TeamService,
        team_id: UUID,
        data: s.TeamOwnershipTransfer,
    ) -> s.TeamDto:
        """Transfer team ownership to another member.

        Only current owner can transfer ownership.

        Args:
            team_id: Team ID
            data: New owner information

        Returns:
            Updated team
        """
        user = request.user

        # Check if user is current owner
        team = await team_service.get(team_id)
        if team.owner_id != user.id and not user.is_superuser:
            raise HTTPException(
                status_code=403,
                detail="Only team owners can transfer ownership"
            )

        # Check if new owner is a team member
        is_member = await team_service.is_member(team_id, data.new_owner_id)
        if not is_member:
            raise HTTPException(
                status_code=400,
                detail="New owner must be a team member"
            )

        return await team_service.transfer_ownership(team_id, data.new_owner_id)

    @get("/{team_id:uuid}/stats")
    async def get_team_stats(
        self,
        team_service: TeamService,
        team_id: UUID,
    ) -> s.TeamStatsDto:
        """Get team statistics.

        Args:
            team_id: Team ID

        Returns:
            Team statistics
        """
        return await team_service.get_team_stats(team_id)
```

---

## Conclusion

Congratulations! You've successfully migrated from Advanced-Alchemy to SQLSpec.

### What you've accomplished

- ✅ Fixed foundation issues (imports, base service)
- ✅ Migrated all services to SQLSpec patterns
- ✅ Updated dependency injection system
- ✅ Migrated routes to use schemas instead of ORM models
- ✅ Maintained frontend compatibility
- ✅ Improved performance and code clarity

### Next steps

1. Monitor application performance
2. Add more comprehensive tests
3. Document any custom patterns you developed
4. Consider adding database migrations for schema changes
5. Train team members on SQLSpec patterns

### Resources

- [SQLSpec Documentation](https://sqlspec.readthedocs.io/)
- [Litestar Documentation](https://docs.litestar.dev/)
- [SQL Builder Patterns](https://sqlspec.readthedocs.io/en/latest/sql-builder/)

Remember: The migration is iterative. Start with one service, test thoroughly, then move to the next. Good luck!
