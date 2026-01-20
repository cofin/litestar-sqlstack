from sqlstack.lib.schema import CamelizedBaseStruct
from sqlstack.utils.types import Email, Name, Password

__all__ = ("AccountLogin", "AccountRegister")


class AccountLogin(CamelizedBaseStruct):
    username: str
    password: Password


class AccountRegister(CamelizedBaseStruct):
    email: Email
    password: Password
    name: Name | None = None
