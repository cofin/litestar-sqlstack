"""Unit tests for DTO utilities."""

from __future__ import annotations

from litestar.dto.config import DTOConfig

from sqlstack.utils.dto import DataclassDTO, config, dto_field


class TestDTOConfig:
    """Test DTO config function."""

    def test_config_defaults(self) -> None:
        """Test config with default values."""
        result = config()

        assert isinstance(result, DTOConfig), "Should return DTOConfig"
        assert result.rename_strategy == "camel", "Default rename strategy should be camel"
        assert result.max_nested_depth == 2, "Default max nested depth should be 2"

    def test_config_with_include(self) -> None:
        """Test config with include parameter."""
        include_fields = {"field1", "field2"}

        result = config(include=include_fields)

        assert result.include == include_fields

    def test_config_with_exclude(self) -> None:
        """Test config with exclude parameter."""
        exclude_fields = {"secret", "internal"}

        result = config(exclude=exclude_fields)

        assert result.exclude == exclude_fields

    def test_config_with_rename_fields(self) -> None:
        """Test config with rename_fields parameter."""
        rename_map = {"old_name": "newName", "other_field": "otherField"}

        result = config(rename_fields=rename_map)

        assert result.rename_fields == rename_map

    def test_config_with_rename_strategy(self) -> None:
        """Test config with custom rename_strategy."""
        result = config(rename_strategy="pascal")

        assert result.rename_strategy == "pascal"

    def test_config_with_max_nested_depth(self) -> None:
        """Test config with custom max_nested_depth."""
        result = config(max_nested_depth=5)

        assert result.max_nested_depth == 5

    def test_config_with_partial(self) -> None:
        """Test config with partial parameter."""
        result = config(partial=True)

        assert result.partial is True

    def test_config_all_parameters(self) -> None:
        """Test config with all parameters."""
        include_fields = {"field1"}
        exclude_fields = {"field2"}
        rename_map = {"old": "new"}

        result = config(
            include=include_fields,
            exclude=exclude_fields,
            rename_fields=rename_map,
            rename_strategy="snake",
            max_nested_depth=3,
            partial=True,
        )

        assert result.include == include_fields
        assert result.exclude == exclude_fields
        assert result.rename_fields == rename_map
        assert result.rename_strategy == "snake"
        assert result.max_nested_depth == 3
        assert result.partial is True

    def test_config_none_values(self) -> None:
        """Test config with None values uses defaults."""
        result = config(include=None, exclude=None, rename_fields=None, rename_strategy=None, max_nested_depth=None, partial=None)

        # Should use defaults when None
        assert result.rename_strategy == "camel"
        assert result.max_nested_depth == 2

    def test_config_empty_include(self) -> None:
        """Test config with empty include set."""
        result = config(include=set())

        assert result.include == set()

    def test_config_empty_exclude(self) -> None:
        """Test config with empty exclude set."""
        result = config(exclude=set())

        assert result.exclude == set()


class TestDataclassDTO:
    """Test DataclassDTO import."""

    def test_dataclass_dto_import(self) -> None:
        """Test DataclassDTO can be imported."""
        assert DataclassDTO is not None
        # Verify it's the correct Litestar class
        from litestar.dto import DataclassDTO as LitestarDataclassDTO

        assert DataclassDTO is LitestarDataclassDTO


class TestDTOField:
    """Test dto_field import."""

    def test_dto_field_import(self) -> None:
        """Test dto_field can be imported."""
        assert dto_field is not None
        # Verify it's the correct Litestar function
        from litestar.dto import dto_field as litestar_dto_field

        assert dto_field is litestar_dto_field


class TestDTOConfigClass:
    """Test DTOConfig class import."""

    def test_dto_config_import(self) -> None:
        """Test DTOConfig can be imported."""
        from sqlstack.utils.dto import DTOConfig as ImportedDTOConfig

        assert ImportedDTOConfig is not None
        # Verify it's the correct Litestar class
        from litestar.dto.config import DTOConfig as LitestarDTOConfig

        assert ImportedDTOConfig is LitestarDTOConfig


class TestModuleExports:
    """Test module __all__ exports."""

    def test_all_exports(self) -> None:
        """Test that __all__ contains expected exports."""
        from sqlstack.utils import dto

        expected_exports = {"DTOConfig", "DataclassDTO", "config", "dto_field"}

        assert hasattr(dto, "__all__"), "Module should have __all__"
        assert set(dto.__all__) == expected_exports, "Should export all DTO utilities"


class TestConfigRenameStrategies:
    """Test different rename strategies."""

    def test_config_camel_case(self) -> None:
        """Test camel case rename strategy (default)."""
        result = config(rename_strategy="camel")

        assert result.rename_strategy == "camel"

    def test_config_pascal_case(self) -> None:
        """Test pascal case rename strategy."""
        result = config(rename_strategy="pascal")

        assert result.rename_strategy == "pascal"

    def test_config_snake_case(self) -> None:
        """Test snake case rename strategy."""
        result = config(rename_strategy="snake")

        assert result.rename_strategy == "snake"


class TestConfigNestedDepth:
    """Test max_nested_depth configurations."""

    def test_config_depth_zero(self) -> None:
        """Test depth 0 (no nesting)."""
        result = config(max_nested_depth=0)

        assert result.max_nested_depth == 0

    def test_config_depth_one(self) -> None:
        """Test depth 1 (one level)."""
        result = config(max_nested_depth=1)

        assert result.max_nested_depth == 1

    def test_config_depth_deep(self) -> None:
        """Test deep nesting."""
        result = config(max_nested_depth=10)

        assert result.max_nested_depth == 10


class TestConfigPartial:
    """Test partial parameter."""

    def test_config_partial_true(self) -> None:
        """Test partial=True."""
        result = config(partial=True)

        assert result.partial is True

    def test_config_partial_false(self) -> None:
        """Test partial=False."""
        result = config(partial=False)

        assert result.partial is False


class TestConfigFieldFiltering:
    """Test field include/exclude filtering."""

    def test_config_include_single_field(self) -> None:
        """Test including single field."""
        result = config(include={"id"})

        assert result.include == {"id"}

    def test_config_exclude_multiple_fields(self) -> None:
        """Test excluding multiple fields."""
        result = config(exclude={"password", "secret_key", "internal_id"})

        assert result.exclude == {"password", "secret_key", "internal_id"}

    def test_config_include_and_exclude(self) -> None:
        """Test both include and exclude (edge case)."""
        # Note: Typically you'd use one or the other, but testing that both can be set
        result = config(include={"id", "name"}, exclude={"password"})

        assert result.include == {"id", "name"}
        assert result.exclude == {"password"}


class TestConfigRenameFields:
    """Test field renaming."""

    def test_config_rename_single_field(self) -> None:
        """Test renaming single field."""
        result = config(rename_fields={"user_id": "userId"})

        assert result.rename_fields == {"user_id": "userId"}

    def test_config_rename_multiple_fields(self) -> None:
        """Test renaming multiple fields."""
        renames = {"user_id": "userId", "created_at": "createdAt", "is_active": "isActive"}

        result = config(rename_fields=renames)

        assert result.rename_fields == renames

    def test_config_empty_rename_fields(self) -> None:
        """Test with empty rename_fields dict."""
        result = config(rename_fields={})

        assert result.rename_fields == {}
