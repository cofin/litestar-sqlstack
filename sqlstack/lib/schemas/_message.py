"""Generic message schema for API responses."""

from sqlstack.lib.schema import CamelizedBaseStruct


class Message(CamelizedBaseStruct):
    """Generic message response schema."""

    message: str
