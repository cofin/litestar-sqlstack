"""Unit tests for environment variable parsing utilities."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from sqlstack.utils.env import BASE_DIR, TRUE_VALUES, UnsetType, get_config_val, get_env


class TestBaseDir:
    """Test BASE_DIR constant."""

    def test_base_dir_is_path(self) -> None:
        """Test BASE_DIR is a Path object."""
        assert isinstance(BASE_DIR, Path), "BASE_DIR should be Path"

    def test_base_dir_exists(self) -> None:
        """Test BASE_DIR exists."""
        assert BASE_DIR.exists(), "BASE_DIR should exist"

    def test_base_dir_is_parent(self) -> None:
        """Test BASE_DIR is parent of sqlstack package."""
        sqlstack_dir = BASE_DIR / "sqlstack"
        assert sqlstack_dir.exists(), "sqlstack directory should exist under BASE_DIR"


class TestTrueValues:
    """Test TRUE_VALUES constant."""

    def test_true_values_frozenset(self) -> None:
        """Test TRUE_VALUES is a frozenset."""
        assert isinstance(TRUE_VALUES, frozenset), "TRUE_VALUES should be frozenset"

    def test_true_values_content(self) -> None:
        """Test TRUE_VALUES contains expected values."""
        expected = {"True", "true", "1", "yes", "YES", "Y", "y", "T", "t"}
        assert expected == TRUE_VALUES, "TRUE_VALUES should contain all true representations"


class TestGetConfigValString:
    """Test get_config_val with string type."""

    def test_get_config_val_string_found(self) -> None:
        """Test getting string value from environment."""
        with patch.dict(os.environ, {"TEST_STRING": "hello"}):
            result = get_config_val("TEST_STRING", default="default")
            assert result == "hello"
            assert isinstance(result, str)

    def test_get_config_val_string_not_found(self) -> None:
        """Test getting string default when not in environment."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_config_val("NONEXISTENT", default="default")
            assert result == "default"

    def test_get_config_val_string_empty(self) -> None:
        """Test getting empty string from environment."""
        with patch.dict(os.environ, {"TEST_EMPTY": ""}):
            result = get_config_val("TEST_EMPTY", default="default")
            assert result == ""


class TestGetConfigValInt:
    """Test get_config_val with int type."""

    def test_get_config_val_int_found(self) -> None:
        """Test getting int value from environment."""
        with patch.dict(os.environ, {"TEST_INT": "42"}):
            result = get_config_val("TEST_INT", default=0)
            assert result == 42
            assert isinstance(result, int)

    def test_get_config_val_int_not_found(self) -> None:
        """Test getting int default when not in environment."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_config_val("NONEXISTENT", default=99)
            assert result == 99

    def test_get_config_val_int_negative(self) -> None:
        """Test getting negative int from environment."""
        with patch.dict(os.environ, {"TEST_NEG": "-10"}):
            result = get_config_val("TEST_NEG", default=0)
            assert result == -10

    def test_get_config_val_int_zero(self) -> None:
        """Test getting zero from environment."""
        with patch.dict(os.environ, {"TEST_ZERO": "0"}):
            result = get_config_val("TEST_ZERO", default=99)
            assert result == 0


class TestGetConfigValBool:
    """Test get_config_val with bool type."""

    def test_get_config_val_bool_true_values(self) -> None:
        """Test various true values."""
        for true_value in TRUE_VALUES:
            with patch.dict(os.environ, {"TEST_BOOL": true_value}):
                result = get_config_val("TEST_BOOL", default=False)
                assert result is True, f"{true_value} should be True"

    def test_get_config_val_bool_false_values(self) -> None:
        """Test false values."""
        false_values = ["False", "false", "0", "no", "NO", "N", "n", "F", "f", ""]
        for false_value in false_values:
            with patch.dict(os.environ, {"TEST_BOOL": false_value}):
                result = get_config_val("TEST_BOOL", default=True)
                assert result is False, f"{false_value} should be False"

    def test_get_config_val_bool_not_found(self) -> None:
        """Test getting bool default when not in environment."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_config_val("NONEXISTENT", default=True)
            assert result is True


class TestGetConfigValPath:
    """Test get_config_val with Path type."""

    def test_get_config_val_path_found(self) -> None:
        """Test getting Path value from environment."""
        test_path = Path(tempfile.gettempdir()) / "env-path-test"
        with patch.dict(os.environ, {"TEST_PATH": str(test_path)}):
            result = get_config_val("TEST_PATH", default=Path("/default"))
            assert result == test_path
            assert isinstance(result, Path)

    def test_get_config_val_path_not_found(self) -> None:
        """Test getting Path default when not in environment."""
        default = Path("/default/path")
        with patch.dict(os.environ, {}, clear=True):
            result = get_config_val("NONEXISTENT", default=default)
            assert result == default

    def test_get_config_val_path_relative(self) -> None:
        """Test getting relative path."""
        with patch.dict(os.environ, {"TEST_PATH": "relative/path"}):
            result = get_config_val("TEST_PATH", default=Path())
            assert result == Path("relative/path")


class TestGetConfigValList:
    """Test get_config_val with list types."""

    def test_get_config_val_list_str_comma_separated(self) -> None:
        """Test parsing comma-separated list of strings."""
        with patch.dict(os.environ, {"TEST_LIST": "a,b,c"}):
            result = get_config_val("TEST_LIST", default=["default"])
            assert result == ["a", "b", "c"]

    def test_get_config_val_list_str_json(self) -> None:
        """Test parsing JSON list of strings."""
        with patch.dict(os.environ, {"TEST_LIST": '["a", "b", "c"]'}):
            result = get_config_val("TEST_LIST", default=["default"])
            assert result == ["a", "b", "c"]

    def test_get_config_val_list_path_comma_separated(self) -> None:
        """Test parsing comma-separated list of Paths."""
        root = Path(tempfile.gettempdir())
        path_values = [root / "one", root / "two", root / "three"]
        with patch.dict(os.environ, {"TEST_PATHS": ",".join(str(path) for path in path_values)}):
            result = get_config_val("TEST_PATHS", default=[Path("/default")])
            assert result == path_values

    def test_get_config_val_list_path_json(self) -> None:
        """Test parsing JSON list of Paths."""
        root = Path(tempfile.gettempdir())
        path_values = [root / "a", root / "b", root / "c"]
        with patch.dict(os.environ, {"TEST_PATHS": json.dumps([str(path) for path in path_values])}):
            result = get_config_val("TEST_PATHS", default=[Path("/default")])
            assert result == path_values

    def test_get_config_val_list_empty(self) -> None:
        """Test getting empty list default."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_config_val("NONEXISTENT", default=[])
            assert result == []

    def test_get_config_val_list_with_spaces(self) -> None:
        """Test parsing list with spaces."""
        with patch.dict(os.environ, {"TEST_LIST": "a, b, c"}):
            result = get_config_val("TEST_LIST", default=["default"])
            assert result == ["a", "b", "c"], "Should strip whitespace"


class TestGetConfigValDict:
    """Test get_config_val with dict type."""

    def test_get_config_val_dict_json(self) -> None:
        """Test parsing JSON dict."""
        with patch.dict(os.environ, {"TEST_DICT": '{"key1": "value1", "key2": "value2"}'}):
            result = get_config_val("TEST_DICT", default={})
            assert result == {"key1": "value1", "key2": "value2"}

    def test_get_config_val_dict_comma_separated(self) -> None:
        """Test parsing comma-separated key=value dict."""
        with patch.dict(os.environ, {"TEST_DICT": "key1=value1,key2=value2"}):
            result = get_config_val("TEST_DICT", default={})
            assert result == {"key1": "value1", "key2": "value2"}

    def test_get_config_val_dict_not_found(self) -> None:
        """Test getting dict default when not in environment."""
        default = {"default": "value"}
        with patch.dict(os.environ, {}, clear=True):
            result = get_config_val("NONEXISTENT", default=default)
            assert result == default

    def test_get_config_val_dict_empty(self) -> None:
        """Test getting empty dict default."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_config_val("NONEXISTENT", default={})
            assert result == {}

    def test_get_config_val_dict_with_spaces(self) -> None:
        """Test parsing dict with spaces."""
        with patch.dict(os.environ, {"TEST_DICT": "key1 = value1, key2 = value2"}):
            result = get_config_val("TEST_DICT", default={})
            assert result == {"key1": "value1", "key2": "value2"}


class TestGetConfigValTypeHint:
    """Test get_config_val with explicit type hint."""

    def test_get_config_val_type_hint_str(self) -> None:
        """Test with explicit str type hint."""
        with patch.dict(os.environ, {"TEST_VAR": "value"}):
            result = get_config_val("TEST_VAR", default=None, type_hint=str)
            assert result == "value"
            assert isinstance(result, str)

    def test_get_config_val_type_hint_int(self) -> None:
        """Test with explicit int type hint."""
        with patch.dict(os.environ, {"TEST_VAR": "42"}):
            result = get_config_val("TEST_VAR", default=None, type_hint=int)
            assert result == 42
            assert isinstance(result, int)

    def test_get_config_val_type_hint_bool(self) -> None:
        """Test with explicit bool type hint."""
        with patch.dict(os.environ, {"TEST_VAR": "true"}):
            result = get_config_val("TEST_VAR", default=None, type_hint=bool)
            assert result is True

    def test_get_config_val_type_hint_path(self) -> None:
        """Test with explicit Path type hint."""
        temp_path = Path(tempfile.gettempdir()) / "explicit-path"
        with patch.dict(os.environ, {"TEST_VAR": str(temp_path)}):
            result = get_config_val("TEST_VAR", default=None, type_hint=Path)
            assert result == temp_path
            assert isinstance(result, Path)

    def test_get_config_val_type_hint_list_str(self) -> None:
        """Test with explicit list[str] type hint."""
        with patch.dict(os.environ, {"TEST_VAR": "a,b,c"}):
            result = get_config_val("TEST_VAR", default=None, type_hint=list[str])
            assert result == ["a", "b", "c"]

    def test_get_config_val_type_hint_list_path(self) -> None:
        """Test with explicit list[Path] type hint."""
        root = Path(tempfile.gettempdir())
        selected = [root / "first", root / "second"]
        with patch.dict(os.environ, {"TEST_VAR": ",".join(str(path) for path in selected)}):
            result = get_config_val("TEST_VAR", default=None, type_hint=list[Path])
            assert result == selected

    def test_get_config_val_type_hint_dict(self) -> None:
        """Test with explicit dict type hint."""
        with patch.dict(os.environ, {"TEST_VAR": '{"key": "value"}'}):
            result = get_config_val("TEST_VAR", default=None, type_hint=dict[str, Any])
            assert result == {"key": "value"}


class TestGetEnv:
    """Test get_env function (returns callable)."""

    def test_get_env_returns_callable(self) -> None:
        """Test get_env returns a callable."""
        getter = get_env("TEST_VAR", default="default")
        assert callable(getter), "get_env should return callable"

    def test_get_env_callable_execution(self) -> None:
        """Test executing callable returned by get_env."""
        with patch.dict(os.environ, {"TEST_VAR": "value"}):
            getter = get_env("TEST_VAR", default="default")
            result = getter()
            assert result == "value"

    def test_get_env_callable_with_default(self) -> None:
        """Test callable uses default when var not found."""
        with patch.dict(os.environ, {}, clear=True):
            getter = get_env("NONEXISTENT", default="default_value")
            result = getter()
            assert result == "default_value"

    def test_get_env_string(self) -> None:
        """Test get_env with string type."""
        with patch.dict(os.environ, {"TEST_STR": "hello"}):
            getter = get_env("TEST_STR", default="")
            assert getter() == "hello"

    def test_get_env_int(self) -> None:
        """Test get_env with int type."""
        with patch.dict(os.environ, {"TEST_INT": "42"}):
            getter = get_env("TEST_INT", default=0)
            assert getter() == 42

    def test_get_env_bool(self) -> None:
        """Test get_env with bool type."""
        with patch.dict(os.environ, {"TEST_BOOL": "true"}):
            getter = get_env("TEST_BOOL", default=False)
            assert getter() is True


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_get_config_val_none_default(self) -> None:
        """Test with None as default."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_config_val("NONEXISTENT", default=None)
            assert result is None

    def test_get_config_val_none_with_value(self) -> None:
        """Test None default but value exists."""
        with patch.dict(os.environ, {"TEST_VAR": "value"}):
            result = get_config_val("TEST_VAR", default=None)
            assert result == "value"

    def test_get_config_val_invalid_int(self) -> None:
        """Test parsing invalid int raises error."""
        with patch.dict(os.environ, {"TEST_INT": "not-a-number"}), pytest.raises(ValueError):
            get_config_val("TEST_INT", default=0)

    def test_get_config_val_invalid_json_list(self) -> None:
        """Test parsing invalid JSON list raises error."""
        with patch.dict(os.environ, {"TEST_LIST": "[invalid json"}), pytest.raises(ValueError):
            get_config_val("TEST_LIST", default=["default"])

    def test_get_config_val_invalid_json_dict(self) -> None:
        """Test parsing invalid JSON dict raises error."""
        with patch.dict(os.environ, {"TEST_DICT": "{invalid json"}), pytest.raises(TypeError):
            get_config_val("TEST_DICT", default={})

    def test_get_config_val_dict_missing_equals(self) -> None:
        """Test parsing dict without = raises error."""
        with patch.dict(os.environ, {"TEST_DICT": "key1:value1"}), pytest.raises(TypeError, match="missing '='"):
            get_config_val("TEST_DICT", default={})


class TestUnsetType:
    """Test UnsetType placeholder."""

    def test_unset_type_class(self) -> None:
        """Test UnsetType is a class."""
        assert isinstance(UnsetType, type), "UnsetType should be a class"

    def test_unset_type_instance(self) -> None:
        """Test creating UnsetType instance."""
        unset = UnsetType()
        assert unset is not None
