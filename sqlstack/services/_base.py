"""Base service module for sqlspec."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, TypeVar, cast

import sqlglot
from sqlglot import exp
from sqlspec.core.filters import (
    AnyCollectionFilter,
    BeforeAfterFilter,
    FilterTypes,
    FilterTypeT,
    InAnyFilter,
    InCollectionFilter,
    LimitOffsetFilter,
    NotAnyCollectionFilter,
    NotInCollectionFilter,
    NotInSearchFilter,
    OffsetPagination,
    OnBeforeAfterFilter,
    OrderByFilter,
    PaginationFilter,
    SearchFilter,
    StatementFilter,
    apply_filter,
)
from sqlspec.typing import ModelDTOT, StatementParameters

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Sequence

    from sqlspec import QueryBuilder, Statement, StatementConfig
    from sqlspec.adapters.asyncpg import AsyncpgDriver

__all__ = (
    "AnyCollectionFilter",
    "BeforeAfterFilter",
    "FilterTypeT",
    "FilterTypes",
    "InAnyFilter",
    "InCollectionFilter",
    "LimitOffsetFilter",
    "NotAnyCollectionFilter",
    "NotInCollectionFilter",
    "NotInSearchFilter",
    "OffsetPagination",
    "OnBeforeAfterFilter",
    "OrderByFilter",
    "PaginationFilter",
    "SQLSpecService",
    "SearchFilter",
    "StatementFilter",
    "apply_filter",
)

T = TypeVar("T")


class SQLSpecService:
    """Base service class for SQLSpec operations."""

    def __init__(self, driver: AsyncpgDriver) -> None:
        """Initialize the service."""
        self.driver = driver

    async def paginate(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters | StatementFilter,
        schema_type: type[ModelDTOT],
        statement_config: StatementConfig | None = None,
    ) -> OffsetPagination[ModelDTOT]:
        """Paginate the data."""
        results, total = await self.driver.select_with_total(
            statement, *parameters, schema_type=schema_type, statement_config=statement_config
        )
        limit_offset = self.find_filter(LimitOffsetFilter, parameters)
        offset = limit_offset.offset if limit_offset else 0
        limit = limit_offset.limit if limit_offset else 10
        return OffsetPagination[ModelDTOT](items=results, limit=limit, offset=offset, total=total)

    async def get_or_404(
        self,
        statement: Statement | QueryBuilder,
        /,
        *parameters: StatementParameters,
        schema_type: type[ModelDTOT],
        error_message: str | None = None,
        statement_config: StatementConfig | None = None,
    ) -> ModelDTOT:
        """Get a single record or raise 404 error if not found.

        Args:
            statement: The SQL statement to execute
            *parameters: Statement parameters
            schema_type: The schema type for the result
            error_message: Custom error message (optional)
            statement_config: Optional statement configuration

        Returns:
            The found record

        Raises:
            ValueError: If no record is found
        """
        result = await self.driver.select_one_or_none(
            statement, *parameters, schema_type=schema_type, statement_config=statement_config
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
    ) -> bool:
        """Check if a record exists.

        Args:
            statement: The SQL statement to execute
            *parameters: Statement parameters
            statement_config: Optional statement configuration

        Returns:
            True if record exists, False otherwise
        """
        result = await self.driver.select_one_or_none(statement, *parameters, statement_config=statement_config)
        return result is not None

    @staticmethod
    def find_filter(
        filter_type: type[FilterTypeT],
        filters: Sequence[StatementFilter | StatementParameters] | Sequence[StatementFilter],
    ) -> FilterTypeT | None:
        """Get the filter specified by filter type from the filters.

        Args:
            filter_type: The type of filter to find.
            filters: filter types to apply to the query

        Returns:
            The match filter instance or None
        """
        return next(
            (cast("FilterTypeT | None", filter_) for filter_ in filters if isinstance(filter_, filter_type)),
            None,
        )

    def with_only_select(self, statement: Statement | QueryBuilder) -> str:
        """Create a COUNT query string from a SELECT statement using SQLGlot AST parsing.

        This method transforms a SELECT statement into a COUNT(*) query by:
        1. Parsing the SQL statement using SQLGlot
        2. Preserving WHERE, HAVING, and GROUP BY clauses
        3. Removing ORDER BY, LIMIT, and OFFSET clauses
        4. Replacing SELECT columns with COUNT(*)

        Args:
            statement: The original SELECT statement or QueryBuilder

        Returns:
            A COUNT query SQL string

        Raises:
            TypeError: If the statement is not a SELECT query
        """
        # Handle QueryBuilder - build it to get SafeQuery
        if hasattr(statement, "build"):
            safe_query = statement.build()  # type: ignore[attr-defined]
            sql_string = safe_query.sql
        elif hasattr(statement, "expression") and statement.expression:
            # This is already an SQL object with expression
            sql_string = str(statement.expression)
        else:
            # This is a string or SQL object without expression
            sql_string = str(statement)

        # Parse the SQL using SQLGlot directly
        try:
            expr = sqlglot.parse_one(sql_string, dialect="postgres")
        except Exception as e:
            msg = f"Failed to parse SQL statement: {e}"
            raise ValueError(msg) from e

        if not isinstance(expr, exp.Select):
            msg = "with_only_select can only be used with SELECT statements"
            raise TypeError(msg)

        # Create count query based on whether there's a GROUP BY clause
        if expr.args.get("group"):
            # For grouped queries, wrap in subquery and count
            subquery = expr.subquery(alias="grouped_data")
            count_expr = exp.select(exp.Count(this=exp.Star())).from_(subquery)
        else:
            # For simple queries, create COUNT(*) with same FROM and WHERE
            count_expr = exp.select(exp.Count(this=exp.Star())).from_(
                cast("exp.Expression", expr.args.get("from")), copy=False
            )
            if expr.args.get("where"):
                count_expr = count_expr.where(cast("exp.Expression", expr.args.get("where")), copy=False)
            if expr.args.get("having"):
                count_expr = count_expr.having(cast("exp.Expression", expr.args.get("having")), copy=False)

        # Remove ordering and pagination clauses from count query
        count_expr.set("order", None)
        count_expr.set("limit", None)
        count_expr.set("offset", None)

        # Return the SQL string
        return count_expr.sql(dialect="postgres")

    async def begin(self) -> None:
        """Begin a database transaction.

        This method starts a new database transaction. You must call either
        commit() or rollback() to complete the transaction, or use the
        begin_transaction() context manager for automatic handling.

        Raises:
            DatabaseError: If the transaction cannot be started
        """
        await self.driver.begin()

    async def commit(self) -> None:
        """Commit the current database transaction.

        This method commits all changes made during the current transaction.
        The transaction must have been started with begin().

        Raises:
            DatabaseError: If the transaction cannot be committed
        """
        await self.driver.commit()

    async def rollback(self) -> None:
        """Rollback the current database transaction.

        This method rolls back all changes made during the current transaction.
        The transaction must have been started with begin().

        Raises:
            DatabaseError: If the transaction cannot be rolled back
        """
        await self.driver.rollback()

    @asynccontextmanager
    async def begin_transaction(self) -> AsyncGenerator[None, None]:
        """Async context manager for database transactions.

        Provides a convenient way to execute multiple operations within a transaction.
        Automatically commits on success or rolls back on error.

        Usage:
            # Automatic transaction management (recommended)
            async with service.begin_transaction():
                await service.create(data1)
                await service.update(id, data2)
                # Commits automatically if no exceptions
            # Rolls back automatically if any exceptions occur

            # Manual transaction management (if needed)
            await service.begin()
            try:
                await service.create(data1)
                await service.update(id, data2)
                await service.commit()
            except Exception:
                await service.rollback()
                raise

        Yields:
            None - The context manager handles transaction lifecycle

        Raises:
            Any exceptions from database operations are re-raised after rollback
        """
        try:
            await self.begin()
            yield
            await self.commit()
        except Exception:
            await self.rollback()
            raise
