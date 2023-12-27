from collections.abc import Callable
from typing import Any, Generic, Protocol, TypeVar, cast

_NOT_FOUND = object()


class Cachable(Protocol):
    _cache: dict[str, Any]


T = TypeVar(
    "T",
    bound=Cachable,
    covariant=True,
)
R = TypeVar("R")


class cached_property(Generic[T, R]):
    """functool.cached property is not compatible with pydantic, it is replacing __dict__ that leads to .dict() method
    working not correctly"""

    def __init__(self, func: Callable[[T], R]):
        self.func = func
        self.attrname: str | None = None

    def __set_name__(self, owner: type[T], name: str) -> None:
        self.attrname = name

    def __get__(self, instance: T | None, owner: type[T] = None) -> R:
        if instance is None:
            raise NotImplementedError("can not call on class")
        if self.attrname is None:
            raise TypeError("Cannot use cached_property instance without calling __set_name__ on it.")

        val = instance._cache.get(self.attrname, _NOT_FOUND)
        if val is _NOT_FOUND:
            val = self.func(instance)
            instance._cache[self.attrname] = val
        return cast(R, val)
