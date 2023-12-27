import typing

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, PrivateAttr

from .cache import cached_property
from .enums import EnumServerType, EnumUartType
from .param_desc import ParamDesc
from .tools import safe_int

if typing.TYPE_CHECKING:
    from .base import BaseObject


class HtmlParser(
    BaseModel,
    arbitrary_types_allowed=True,
    keep_untouched=(
        cached_property,
        ParamDesc,
    ),
):
    html: str

    _cache: dict[str, typing.Any] = PrivateAttr(default_factory=dict)

    @cached_property
    def bs(self) -> BeautifulSoup:
        return BeautifulSoup(self.html)


class Cf1(HtmlParser):
    ip = ParamDesc("eip", str)
    password = ParamDesc("pwd", str, maxlength=3)
    gate_way = ParamDesc("gw", str)
    server_ip = ParamDesc("sip", str)
    server_type = ParamDesc("srvt", EnumServerType)
    script = ParamDesc("sct", str, maxlength=15)
    watch_dog = ParamDesc("pr", safe_int)
    long_p = ParamDesc("long_p", safe_int)
    uart = ParamDesc("gsm", EnumUartType)
    gsm_force = ParamDesc("gsmf", bool)

    _param_cache: dict[str, typing.Any] = PrivateAttr(default_factory=dict)


class Cf2(HtmlParser):
    mega_id = ParamDesc("mdid", str, maxlength=5)
    srv_loop = ParamDesc("sl", bool)

    _param_cache: dict[str, typing.Any] = PrivateAttr(default_factory=dict)


class Customization(BaseModel):
    name: typing.Optional[str]
    entity_id: typing.Optional[str]
    platform: typing.Optional[str]


class Config(
    BaseModel,
    arbitrary_types_allowed=True,
    keep_untouched=(
        cached_property,
        ParamDesc,
    ),
):
    version: str = ""
    password: str = "sec"
    objects: list["BaseObject"] = Field(default_factory=list, exclude=True)
    cf1: typing.Union[Cf1, None] = Field(None, exclude={"bs"})
    cf2: typing.Union[Cf2, None] = Field(None, exclude={"bs"})
    customization: dict[str, Customization] = Field(default_factory=dict, exclude=True)
    # словарь кастомизаций, ключ - уникальный id объекта
    _parsed: set[str] = PrivateAttr(default_factory=set)
    _skipped: set[str] = PrivateAttr(default_factory=set)
    _next_paths: set[str] = PrivateAttr(default_factory=lambda: {"/"})

    def add_parsed(self, path: str) -> None:
        p = path.removeprefix(f"/{self.password}")
        self._parsed.add(p)
        self._next_paths.remove(p)

    def add_skipped(self, path: str) -> None:
        p = path.removeprefix(f"/{self.password}")
        self._skipped.add(p)
        self._next_paths.remove(p)

    def add_next(self, path: str) -> None:
        p = path.removeprefix(f"/{self.password}")
        if p not in self._parsed | self._skipped:
            self._next_paths.add(p)
