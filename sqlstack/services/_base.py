"""Base service module - enhanced base service class with convenience methods."""

from typing import TYPE_CHECKING, TypeVar, cast

from sqlspec import sql
from sqlspec.adapters.asyncpg import AsyncpgConnection, AsyncpgDriver
from sqlspec.service import OffsetPagination, SQLSpecAsyncService
from sqlspec.statement.filters import LimitOffsetFilter, StatementFilter

if TYPE_CHECKING:
    from typing import Any

    from sqlspec.statement.builder import Select
    from sqlspec.typing import ModelDTOT

__all__ = (
    "AsyncpgService", 
)

T = TypeVar("T", bound=StatementFilter)
 

class AsyncpgService(SQLSpecAsyncService[AsyncpgDriver, AsyncpgConnection]):
    """Enhanced base service class with convenience methods for common patterns.

    No need for ResultConverter - use the built-in schema_type parameter instead!
    
    Note: The paginate() method is now built into SQLSpec! Just call it directly:
    - await service.paginate(statement, schema_type=User)
    - await service.paginate(statement, LimitOffsetFilter(limit=20, offset=0), schema_type=User)
    """

    async def get_or_404(
        self,
        statement: "Select",
        schema_type: "type[ModelDTOT] | None" = None,
        error_message: str = "Not found",
    ) -> Any:
        """Execute query and raise error if not found.

        Example:
            user = await service.get_or_404(
                sql.select("*").from_("users").where_eq("id", user_id),
                schema_type=schemas.User
            )
        """
        result = await self.select_one_or_none(statement, schema_type=schema_type)
        if result is None:
            raise ValueError(error_message)
        return result

    async def exists(self, statement: "Select") -> bool:
        """Check if any rows match the query.

        Example:
            exists = await service.exists(
                sql.select("1").from_("users").where_eq("email", email)
            )
        """
        # Optimize the query to just check existence
        check_stmt = statement.limit(1).with_only_select(sql.literal(1))
        result = await self.select_one_or_none(check_stmt)
        return result is not None
