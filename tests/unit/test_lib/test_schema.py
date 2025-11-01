from datetime import datetime

import msgspec

from sqlstack.lib import schema


class ExampleStruct(schema.BaseStruct):
    id: int
    optional: int | None = None
    created_at: datetime | msgspec.UnsetType = msgspec.UNSET


class ExampleCamelStruct(schema.CamelizedBaseStruct):
    snake_case: int


class ExampleSchema(schema.BaseSchema):
    value: int


class ExampleCamelSchema(schema.CamelizedBaseSchema):
    snake_case: int


def test_base_struct_to_dict_excludes_unset() -> None:
    instance = ExampleStruct(id=1, optional=None, created_at=msgspec.UNSET)

    data = instance.to_dict()

    assert data == {"id": 1, "optional": None}
    assert "created_at" not in data

    # ensure optional None removal does not mutate instance
    assert instance.optional is None


def test_camelized_base_struct_respects_field_names() -> None:
    instance = ExampleCamelStruct(snake_case=5)

    # Field names remain snake_case for attribute access
    assert instance.snake_case == 5


def test_base_schema_assignment_validation() -> None:
    payload = ExampleSchema(value=1)
    payload.value = 2  # validate_assignment should permit reassignment without error

    assert payload.value == 2


def test_camelized_base_schema_alias_generation() -> None:
    payload = ExampleCamelSchema(snake_case=10)

    assert payload.model_dump(by_alias=True) == {"snakeCase": 10}


def test_message_schema_wraps_message_field() -> None:
    msg = schema.Message(message="hello")

    assert msg.message == "hello"
