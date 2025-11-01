from sqlstack.lib.schema import CamelizedBaseStruct


class Message(CamelizedBaseStruct):
    message: str
