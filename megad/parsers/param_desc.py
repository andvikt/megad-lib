from collections.abc import Callable
from typing import Any, Generic, Protocol, TypeVar, Union

from bs4 import BeautifulSoup, Tag

from .cache import Cachable, cached_property

R = TypeVar("R")


class ObjectData(Cachable, Protocol):
    @cached_property
    def bs(self) -> BeautifulSoup:
        ...


class ParamDesc(Generic[R]):
    """Desciptor, helps to map source html to object attributes"""

    def __init__(
        self,
        name: str,
        type_: type[R] | Callable[[Any], R],
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self.name = name
        self.type_ = type_

    def __set_name__(self, owner: ObjectData, name: str) -> None:
        self.attrname = name

    def __get__(self, obj: Union[ObjectData, None], objtype: Any = None) -> R | None:
        if obj is None:
            return self  # type: ignore
        if v := obj._cache.get(self.name):
            return v  # type: ignore
        el = obj.bs.find(True, {"name": self.name})
        ret = None
        if not isinstance(el, Tag):
            ret = None
        else:
            tag = el.name
            if tag == "select":
                for op in el.find_all("option"):
                    if isinstance(op, Tag):
                        if op.attrs.get("selected", None) is not None:
                            ret = self.type_(int(op.attrs["value"]))  # type: ignore
                            break
            elif tag == "input":
                if el.attrs.get("type") == "checkbox":
                    ret = self.type_(el.attrs.get("checked", None) is not None)  # type: ignore
                else:
                    ret = self.type_(el.attrs["value"])  # type: ignore
        obj._cache[self.name] = ret
        return ret
