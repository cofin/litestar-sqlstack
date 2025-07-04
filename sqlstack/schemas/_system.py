from typing import Literal

from sqlstack.__metadata__ import __version__
from sqlstack.lib.settings import get_settings
from sqlstack.schemas._base import CamelizedBaseStruct

__all__ = ("SystemHealth",)

settings = get_settings()


class SystemHealth(CamelizedBaseStruct):
    database_status: Literal["online", "offline"] = "offline"
    app: str = settings.app.NAME
    version: str = __version__
