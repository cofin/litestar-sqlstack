from typing import Literal

from sqlstack.__metadata__ import __version__
from sqlstack.lib.schema import CamelizedBaseStruct
from sqlstack.lib.settings import get_settings

__all__ = ("SystemHealth",)

_settings = get_settings()


class SystemHealth(CamelizedBaseStruct):
    database_status: Literal["online", "offline"] = "offline"
    app: str = _settings.app.NAME
    version: str = __version__
