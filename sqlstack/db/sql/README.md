# SQLSpec Query Files

This directory contains SQL query files for use with SQLSpec's SQLFileLoader.

## File Format

Query files use SQLFileLoader's named query syntax:

```sql
-- name: get-user-by-id
SELECT id, email, name, is_active
FROM user_account
WHERE id = :user_id;

-- name: create-user
INSERT INTO user_account (id, email, name, created_at, updated_at)
VALUES (:id, :email, :name, NOW(), NOW())
RETURNING id, email, name, created_at, updated_at;
```

## File Organization

### Core Entity Files

- `users.sql` - User CRUD operations and management
- `roles.sql` - Role CRUD operations  
- `tags.sql` - Tag management and search operations
- `teams.sql` - Team CRUD operations and search

### Relationship & Specialized Files

- `user_roles.sql` - User-role assignment operations
- `user_oauth_accounts.sql` - OAuth account management
- `team_members.sql` - Team membership management
- `team_tags.sql` - Team-tag relationship operations
- `team_invitations.sql` - Team invitation workflow
- `authentication.sql` - Authentication, password, and verification operations

## Query Naming Conventions

### Query Names

Format: `{action}-{entity}[-{qualifier}]`

Examples:

- `get-user-by-id`
- `create-team-invitation`
- `list-teams-for-user`
- `update-team-member-role`

### Common Actions

- `get-*` - Retrieve single record
- `list-*` - Retrieve multiple records
- `count-*` - Count operations
- `create-*` - Insert operations
- `update-*` - Update operations
- `delete-*` - Delete operations
- `exists-*` - Existence checks
- `search-*` - Search operations

## PostgreSQL Optimizations

All queries are optimized for PostgreSQL:

- Use `gen_random_uuid()` for UUID generation
- Use `NOW()` for timestamps
- Use `COALESCE()` for optional updates
- Use `ON CONFLICT` for upsert operations
- Use `ILIKE` for case-insensitive searches
- Use proper joins and indexing strategies

## Usage with SQLSpec

These queries are automatically loaded by SQLSpec and can be accessed in services:

```python
from sqlstack.config import db_manager

# Using the global db_manager instance (configured in config.py)
class UserService(SQLSpecService):
    async def get_user_by_id(self, user_id: UUID) -> User:
        # Get named statement from loaded SQL files
        stmt = db_manager.get_sql("get-user-by-id")
        
        # Execute with driver
        return await self.driver.select_one(
            stmt,
            {"user_id": user_id},
            schema_type=User
        )
```

## Configuration

SQL files are loaded during application startup in `config.py`:

```python
db_manager = SQLSpec(
    config=[
        DatabaseConfig(commit_mode="autocommit", config=db),
        DatabaseConfig(config=etl_db, connection_key="etl_connection", pool_key="etl_pool", session_key="etl_session"),
    ]
)
db_manager.load_sql_files(BASE_DIR / "db" / "sql")
```
