"""Unit tests for serialization utilities."""

from __future__ import annotations

import datetime
import json
from uuid import UUID

import msgspec
import pytest
from pydantic import BaseModel

from sqlstack.utils.serialization import (
    convert_date_to_iso,
    convert_datetime_to_gmt_iso,
    from_json,
    to_json,
)


class TestToJson:
    """Test to_json function."""

    def test_to_json_simple_dict(self) -> None:
        """Test serializing simple dict."""
        data = {"key": "value", "number": 42}

        result = to_json(data)

        assert isinstance(result, bytes), "Should return bytes"
        assert b"key" in result
        assert b"value" in result
        assert b"42" in result

    def test_to_json_list(self) -> None:
        """Test serializing list."""
        data = ["item1", "item2", "item3"]

        result = to_json(data)

        assert isinstance(result, bytes)
        assert b"item1" in result
        assert b"item2" in result

    def test_to_json_nested_structure(self) -> None:
        """Test serializing nested structure."""
        data = {"outer": {"inner": "value"}, "list": [1, 2, 3]}

        result = to_json(data)

        assert isinstance(result, bytes)
        assert b"outer" in result
        assert b"inner" in result
        assert b"list" in result

    def test_to_json_bytes_input(self) -> None:
        """Test to_json with bytes input (should return as-is)."""
        data = b'{"key": "value"}'

        result = to_json(data)

        assert result == data, "Should return bytes unchanged"

    def test_to_json_uuid(self) -> None:
        """Test serializing UUID."""
        test_uuid = UUID("123e4567-e89b-12d3-a456-426614174000")
        data = {"id": test_uuid}

        result = to_json(data)

        assert isinstance(result, bytes)
        assert b"123e4567-e89b-12d3-a456-426614174000" in result

    def test_to_json_datetime(self) -> None:
        """Test serializing datetime."""
        dt = datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=datetime.UTC)
        data = {"timestamp": dt}

        result = to_json(data)

        assert isinstance(result, bytes)
        assert b"2024-01-15" in result
        assert b"10:30:00" in result

    def test_to_json_date(self) -> None:
        """Test serializing date."""
        d = datetime.date(2024, 1, 15)
        data = {"date": d}

        result = to_json(data)

        assert isinstance(result, bytes)
        assert b"2024-01-15" in result

    def test_to_json_pydantic_model(self) -> None:
        """Test serializing Pydantic model."""

        class TestModel(BaseModel):
            name: str
            value: int

        model = TestModel(name="test", value=42)
        data = {"model": model}

        result = to_json(data)

        assert isinstance(result, bytes)
        assert b"name" in result
        assert b"test" in result
        assert b"value" in result
        assert b"42" in result

    def test_to_json_none(self) -> None:
        """Test serializing None."""
        data = {"key": None}

        result = to_json(data)

        assert isinstance(result, bytes)
        assert b"null" in result

    def test_to_json_boolean(self) -> None:
        """Test serializing boolean."""
        data = {"true_val": True, "false_val": False}

        result = to_json(data)

        assert isinstance(result, bytes)
        assert b"true" in result
        assert b"false" in result

    def test_to_json_empty_dict(self) -> None:
        """Test serializing empty dict."""
        data = {}

        result = to_json(data)

        assert result == b"{}"

    def test_to_json_empty_list(self) -> None:
        """Test serializing empty list."""
        data = []

        result = to_json(data)

        assert result == b"[]"


class TestFromJson:
    """Test from_json function."""

    def test_from_json_bytes_input(self) -> None:
        """Test deserializing from bytes."""
        data = b'{"key": "value", "number": 42}'

        result = from_json(data)

        assert isinstance(result, dict)
        assert result["key"] == "value"
        assert result["number"] == 42

    def test_from_json_string_input(self) -> None:
        """Test deserializing from string."""
        data = '{"key": "value", "number": 42}'

        result = from_json(data)

        assert isinstance(result, dict)
        assert result["key"] == "value"
        assert result["number"] == 42

    def test_from_json_list(self) -> None:
        """Test deserializing list."""
        data = b'["item1", "item2", "item3"]'

        result = from_json(data)

        assert isinstance(result, list)
        assert result == ["item1", "item2", "item3"]

    def test_from_json_nested_structure(self) -> None:
        """Test deserializing nested structure."""
        data = b'{"outer": {"inner": "value"}, "list": [1, 2, 3]}'

        result = from_json(data)

        assert result["outer"]["inner"] == "value"
        assert result["list"] == [1, 2, 3]

    def test_from_json_null(self) -> None:
        """Test deserializing null."""
        data = b'{"key": null}'

        result = from_json(data)

        assert result["key"] is None

    def test_from_json_boolean(self) -> None:
        """Test deserializing boolean."""
        data = b'{"true_val": true, "false_val": false}'

        result = from_json(data)

        assert result["true_val"] is True
        assert result["false_val"] is False

    def test_from_json_number(self) -> None:
        """Test deserializing numbers."""
        data = b'{"int": 42, "float": 3.14, "negative": -10}'

        result = from_json(data)

        assert result["int"] == 42
        assert result["float"] == 3.14
        assert result["negative"] == -10

    def test_from_json_empty_dict(self) -> None:
        """Test deserializing empty dict."""
        data = b"{}"

        result = from_json(data)

        assert result == {}

    def test_from_json_empty_list(self) -> None:
        """Test deserializing empty list."""
        data = b"[]"

        result = from_json(data)

        assert result == []

    def test_from_json_invalid_json(self) -> None:
        """Test deserializing invalid JSON raises error."""
        data = b"{invalid json}"

        with pytest.raises(msgspec.DecodeError):
            from_json(data)


class TestRoundTrip:
    """Test serialization round-trip (to_json -> from_json)."""

    def test_round_trip_dict(self) -> None:
        """Test round-trip with dict."""
        original = {"key": "value", "number": 42, "nested": {"inner": "data"}}

        serialized = to_json(original)
        deserialized = from_json(serialized)

        assert deserialized == original

    def test_round_trip_list(self) -> None:
        """Test round-trip with list."""
        original = ["item1", "item2", "item3", 42, True]

        serialized = to_json(original)
        deserialized = from_json(serialized)

        assert deserialized == original

    def test_round_trip_complex(self) -> None:
        """Test round-trip with complex structure."""
        original = {
            "string": "value",
            "int": 42,
            "float": 3.14,
            "bool": True,
            "none": None,
            "list": [1, 2, 3],
            "nested": {"a": 1, "b": 2},
        }

        serialized = to_json(original)
        deserialized = from_json(serialized)

        assert deserialized == original


class TestConvertDatetimeToGmtIso:
    """Test convert_datetime_to_gmt_iso function."""

    def test_convert_datetime_utc(self) -> None:
        """Test converting UTC datetime."""
        dt = datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=datetime.UTC)

        result = convert_datetime_to_gmt_iso(dt)

        assert result == "2024-01-15T10:30:00Z"

    def test_convert_datetime_naive(self) -> None:
        """Test converting naive datetime (assumes UTC)."""
        dt = datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=datetime.UTC).replace(tzinfo=None)

        result = convert_datetime_to_gmt_iso(dt)

        assert result == "2024-01-15T10:30:00Z"

    def test_convert_datetime_with_timezone(self) -> None:
        """Test converting datetime with timezone (converts to UTC)."""
        import zoneinfo

        # Create datetime in US/Eastern (UTC-5)
        eastern = zoneinfo.ZoneInfo("US/Eastern")
        dt = datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=eastern)

        result = convert_datetime_to_gmt_iso(dt)

        # Should be converted to UTC
        assert result.endswith("Z")
        assert "2024-01-15" in result

    def test_convert_datetime_midnight(self) -> None:
        """Test converting midnight datetime."""
        dt = datetime.datetime(2024, 1, 15, 0, 0, 0, tzinfo=datetime.UTC)

        result = convert_datetime_to_gmt_iso(dt)

        assert result == "2024-01-15T00:00:00Z"

    def test_convert_datetime_with_seconds(self) -> None:
        """Test converting datetime with seconds."""
        dt = datetime.datetime(2024, 1, 15, 10, 30, 45, tzinfo=datetime.UTC)

        result = convert_datetime_to_gmt_iso(dt)

        assert result == "2024-01-15T10:30:45Z"


class TestConvertDateToIso:
    """Test convert_date_to_iso function."""

    def test_convert_date_basic(self) -> None:
        """Test converting basic date."""
        d = datetime.date(2024, 1, 15)

        result = convert_date_to_iso(d)

        assert result == "2024-01-15"

    def test_convert_date_beginning_of_year(self) -> None:
        """Test converting date at beginning of year."""
        d = datetime.date(2024, 1, 1)

        result = convert_date_to_iso(d)

        assert result == "2024-01-01"

    def test_convert_date_end_of_year(self) -> None:
        """Test converting date at end of year."""
        d = datetime.date(2024, 12, 31)

        result = convert_date_to_iso(d)

        assert result == "2024-12-31"

    def test_convert_date_leap_year(self) -> None:
        """Test converting date in leap year."""
        d = datetime.date(2024, 2, 29)  # 2024 is a leap year

        result = convert_date_to_iso(d)

        assert result == "2024-02-29"


class TestDefaultFunction:
    """Test _default function via to_json."""

    def test_default_uuid(self) -> None:
        """Test UUID serialization via _default."""
        test_uuid = UUID("123e4567-e89b-12d3-a456-426614174000")
        data = [test_uuid]

        result = to_json(data)
        deserialized = from_json(result)

        assert deserialized[0] == str(test_uuid)

    def test_default_datetime(self) -> None:
        """Test datetime serialization via _default."""
        dt = datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=datetime.UTC)
        data = [dt]

        result = to_json(data)
        deserialized = from_json(result)

        assert deserialized[0] == "2024-01-15T10:30:00Z"

    def test_default_date(self) -> None:
        """Test date serialization via _default."""
        d = datetime.date(2024, 1, 15)
        data = [d]

        result = to_json(data)
        deserialized = from_json(result)

        assert deserialized[0] == "2024-01-15"

    def test_default_pydantic_model(self) -> None:
        """Test Pydantic model serialization via _default."""

        class User(BaseModel):
            id: int
            name: str

        user = User(id=1, name="Alice")
        data = [user]

        result = to_json(data)
        deserialized = from_json(result)

        # Should be serialized as JSON string
        user_json = json.loads(deserialized[0])
        assert user_json["id"] == 1
        assert user_json["name"] == "Alice"


class TestEdgeCases:
    """Test edge cases and special values."""

    def test_to_json_large_number(self) -> None:
        """Test serializing large number."""
        data = {"large": 9999999999999999999}

        result = to_json(data)

        assert isinstance(result, bytes)
        assert b"9999999999999999999" in result

    def test_to_json_scientific_notation(self) -> None:
        """Test serializing number in scientific notation."""
        data = {"scientific": 1e10}

        result = to_json(data)

        assert isinstance(result, bytes)

    def test_to_json_unicode(self) -> None:
        """Test serializing Unicode characters."""
        data = {"unicode": "Hello 世界 🌍"}

        result = to_json(data)
        deserialized = from_json(result)

        assert deserialized["unicode"] == "Hello 世界 🌍"

    def test_to_json_special_characters(self) -> None:
        """Test serializing special characters."""
        data = {"special": "Line1\nLine2\tTab"}

        result = to_json(data)
        deserialized = from_json(result)

        assert deserialized["special"] == "Line1\nLine2\tTab"

    def test_from_json_whitespace(self) -> None:
        """Test deserializing JSON with whitespace."""
        data = b'  { "key"  :  "value"  }  '

        result = from_json(data)

        assert result == {"key": "value"}
