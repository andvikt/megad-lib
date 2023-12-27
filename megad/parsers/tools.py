import re
import typing
from collections.abc import AsyncIterable, Awaitable, Callable
from contextlib import suppress
from dataclasses import asdict as data_asdict
from dataclasses import fields, is_dataclass
from typing import Any, Protocol, Self, TypeVar

if typing.TYPE_CHECKING:
    from ..core import MegaD
    from ..parsers.param_desc import ObjectData
    from .base import BaseObject


class _Parser(Protocol):
    def __call__(self, mega: "MegaD", path: str, data: str) -> Awaitable[None]:
        ...


T_ = TypeVar("T_", bound="BaseObject")

_parsers: dict[str | re.Pattern[str], _Parser] = {}


def parser(d: str | re.Pattern[str]) -> Callable[[_Parser], _Parser]:
    def deco(foo: _Parser) -> _Parser:
        _parsers[d] = foo
        return foo

    return deco


def get_parser(path: str) -> _Parser | None:
    if p := _parsers.get(path, None):
        return p
    for patt, p in _parsers.items():
        if isinstance(patt, re.Pattern):
            if patt.match(path):
                return p
    return None


def safe_int(val: str) -> int | None:
    if val:
        with suppress(ValueError, TypeError):
            return int(val)
    return None


def safe_float(val: str) -> float | None:
    if val:
        with suppress(ValueError, TypeError):
            return float(val)
    return None


async def get_devices(self: Any) -> AsyncIterable[Any]:
    for _ in []:
        yield


class BaseObjectMeta(type):
    """metacalss that will reset get_devices for each subclass in order to avoid sircular recurrency"""

    _registry: dict[str, type["BaseObject"]] = {}

    def __new__(cls, name: str, bases: Any, dct: Any) -> Self:  # type: ignore
        new_class = super().__new__(cls, name, bases, dct)
        cls._registry[name] = new_class  # type: ignore
        if not bases:
            return new_class
        BaseClass = bases[0]
        if hasattr(new_class, "get_devices"):
            if new_class.get_devices == BaseClass.get_devices:
                new_class.get_devices = get_devices
        return new_class


def as_dict(data: "ObjectData") -> dict[str, int | str | float]:
    from ..parsers.param_desc import ParamDesc

    ret: dict[str, int | str | float] = {}
    for name, value in type(data).__dict__.items():
        if isinstance(value, ParamDesc):
            ret[name] = getattr(data, name)
    return ret


def _get_nested(n: Any) -> dict[str, Any] | Any:
    if is_dataclass(type(n)):
        return data_asdict(n)
    else:
        return n


def asdict(o: T_) -> dict[str, Any]:
    return {
        field.name: _get_nested(getattr(o, field.name))
        for field in fields(o)
        if field.name
        not in {
            "mega",
            "update_callback",
            "_param_cache",
        }
    }
