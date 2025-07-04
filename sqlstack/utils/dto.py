from __future__ import annotations

from typing import TYPE_CHECKING, Any

from litestar.dto import DataclassDTO, dto_field
from litestar.dto.config import DTOConfig
from litestar.plugins.sqlalchemy import SQLAlchemyDTO

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet

    from litestar.dto import RenameStrategy

__all__ = ("DTOConfig", "DataclassDTO", "SQLAlchemyDTO", "config", "dto_field")


def config(
    include: AbstractSet[str] | None = None,
    exclude: AbstractSet[str] | None = None,
    rename_fields: dict[str, str] | None = None,
    rename_strategy: RenameStrategy | None = None,
    max_nested_depth: int | None = None,
    partial: bool | None = None,
) -> DTOConfig:
    """_summary_

    Returns:
        DTOConfig: Configured DTO class

    """
    default_kwargs: dict[str, Any] = {"rename_strategy": "camel", "max_nested_depth": 2}
    if include:
        default_kwargs["include"] = include
    if exclude:
        default_kwargs["exclude"] = exclude
    if rename_fields:
        default_kwargs["rename_fields"] = rename_fields
    if rename_strategy:
        default_kwargs["rename_strategy"] = rename_strategy
    if max_nested_depth:
        default_kwargs["max_nested_depth"] = max_nested_depth
    if partial:
        default_kwargs["partial"] = partial
    return DTOConfig(**default_kwargs)
