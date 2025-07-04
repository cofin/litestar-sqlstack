# SQLSpec Service Improvements Summary

## Overview

This document summarizes the improvements made to your SQLSpec service layer code, demonstrating how to better use SQLSpec's existing features for cleaner, more maintainable code.

## Key Improvements Made

### 1. Removed Unnecessary ResultConverter Mixin

**Before:**

```python
class AsyncpgService(SQLSpecAsyncService, ResultConverter):
    # Manually converting results
```

**After:**

```python
class AsyncpgService(SQLSpecAsyncService[AsyncpgDriver, AsyncpgConnection]):
    # No ResultConverter needed - use built-in schema_type parameter!
```

### 2. Replaced Tuple Syntax with Helper Methods

**Before:**

```python
.where(("id", user_id))          # Confusing tuple syntax
.where(("status", "active"))
```

**After:**

```python
.where_eq("id", user_id)         # Clear and readable!
.where_eq("status", "active")
```

### 3. Used Built-in Schema Conversion

**Before:**

```python
result = await self.driver.execute(stmt)
return self.to_schema(result.one(), schema_type=schemas.User)
```

**After:**

```python
return await self.select_one(stmt, schema_type=schemas.User)
# Automatic conversion with proper type inference!
```

### 4. Added Convenience Helper Methods

**UPDATE**: The `paginate` method is now built into SQLSpec itself! I've added it to the core service classes.

In `_base.py`, added two powerful helper methods:

```python
async def get_or_404(statement, schema_type=None, error_message="Not found"):
    """Execute query and raise error if not found"""

async def exists(statement) -> bool:
    """Check if any rows match the query"""
```

The `paginate` method is now available on all SQLSpec services:

```python
# Basic pagination
result = await service.paginate(
    sql.select("*").from_("users"),
    limit=10,
    offset=20
)

# With schema conversion
result = await service.paginate(
    sql.select("*").from_("users"),
    schema_type=User,
    limit=10
)

# With filters (LimitOffsetFilter overrides default limit/offset)
result = await service.paginate(
    sql.select("*").from_("users"),
    OrderByFilter("created_at", "desc"),
    LimitOffsetFilter(limit=20, offset=40),
    schema_type=User
)
```

### 5. Used Service Methods Instead of Driver

**Before:**

```python
result = await self.driver.execute(stmt)
items = result.all()
```

**After:**

```python
items = await self.select(stmt, schema_type=schemas.User)
# or
item = await self.select_one(stmt, schema_type=schemas.User)
# or
value = await self.select_value(stmt)  # For scalar values
```

## WHERE Clause Helper Methods Available

SQLSpec has extensive WHERE clause helpers that are more readable than tuple syntax:

### Equality and Comparison

- `.where_eq("col", val)` - column = value
- `.where_ne("col", val)` - column != value
- `.where_gt("col", val)` - column > value
- `.where_gte("col", val)` - column >= value
- `.where_lt("col", val)` - column < value
- `.where_lte("col", val)` - column <= value

### Pattern Matching

- `.where_like("col", "%pattern%")` - LIKE pattern matching
- `.where_ilike("col", "%pattern%")` - Case-insensitive LIKE
- `.where_not_like("col", "%pattern%")` - NOT LIKE

### NULL Checks

- `.where_is_null("col")` - IS NULL
- `.where_is_not_null("col")` - IS NOT NULL

### IN Clauses

- `.where_in("col", [1, 2, 3])` - IN list
- `.where_in("col", subquery)` - IN subquery
- `.where_not_in("col", values)` - NOT IN

### Range Checks

- `.where_between("col", start, end)` - BETWEEN range

### Multiple Conditions

```python
stmt = (
    sql.select("*")
    .from_("users")
    .where_eq("is_active", True)
    .where_gte("age", 18)
    .where_like("email", "%@company.com")
)
```

## Complex Query Examples Added

### Search with Pattern Matching

```python
async def search(self, query: str) -> list[schemas.Tag]:
    stmt = (
        sql.select("*")
        .from_("tag")
        .where(
            sql.raw(
                "(LOWER(name) LIKE LOWER(:pattern) OR LOWER(description) LIKE LOWER(:pattern))",
                pattern=f"%{query}%"
            )
        )
    )
    return await self.select(stmt, schema_type=schemas.Tag)
```

### Subquery with WHERE IN

```python
if user and not self.can_view_all(user):
    member_subquery = (
        sql.select("team_id")
        .from_("team_member")
        .where_eq("user_id", user.id)
    )
    stmt = stmt.where_in("t.id", member_subquery)
```

### JOIN with GROUP BY and HAVING

```python
async def get_popular_tags(self, min_usage: int = 5) -> list[schemas.Tag]:
    stmt = (
        sql.select("t.*", sql.raw("COUNT(it.item_id) as usage_count"))
        .from_("tag t")
        .left_join("item_tag it", sql.raw("it.tag_id = t.id"))
        .group_by(sql.raw("t.id"))
        .having(sql.raw("COUNT(it.item_id) >= :min_usage", min_usage=min_usage))
        .order_by(sql.raw("usage_count DESC"))
    )
    return await self.select(stmt, schema_type=schemas.Tag)
```

## Transaction Handling

Transactions work seamlessly with service methods:

```python
async with self.driver.transaction():
    # All service methods work within the transaction
    team = await self.select_one(stmt, schema_type=s.Team)
    await self.execute(member_stmt)
    await self._update_team_tags(team_id, tags)
    # Automatic commit on success, rollback on error
```

## Benefits of These Changes

1. **Better Readability**: `where_eq("id", user_id)` is clearer than `("id", user_id)`
2. **Type Safety**: Built-in `schema_type` parameter provides proper type inference
3. **Less Boilerplate**: No need for manual `to_schema()` conversions
4. **Consistency**: All queries follow the same pattern
5. **Error Handling**: `get_or_404()` provides better UX
6. **Performance**: `paginate()` efficiently handles count + data queries

## Migration Guide

To update your other services:

1. Remove `ResultConverter` from class inheritance
2. Replace `("column", value)` with `.where_eq("column", value)`
3. Replace `driver.execute()` + `to_schema()` with service methods + `schema_type`
4. Use `paginate()` helper instead of manual pagination logic
5. Use `get_or_404()` for single record fetches that must exist
6. Use `exists()` instead of count queries for existence checks

## Next Steps

1. Update remaining service files following these patterns
2. Create a "Best Practices" document for your team
3. Consider adding more domain-specific helpers to your base service
4. Look into SQLSpec's filter system for more advanced query building

The key insight: SQLSpec already has the features users want - they just need to be more discoverable!
