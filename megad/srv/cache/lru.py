import typing

from .dlist import DList, Node

R = typing.TypeVar("R")
K = typing.TypeVar("K")
T = typing.TypeVar("T")


class _NotSet:
    pass


NOTSET = _NotSet()


class LRU(typing.MutableMapping[K, R]):
    def __init__(self, max_size: int) -> None:
        super().__init__()
        self._data: dict[K, Node[tuple[K, R]] | _NotSet] = {}
        self._l: DList[tuple[K, R]] = DList()
        self._max_size = max_size

    @typing.overload
    def get(
        self,
        key: K,
        /,
    ) -> R | None:
        ...

    @typing.overload
    def get(
        self,
        key: K,
        /,
        default: R | T,
    ) -> R | T:
        ...

    def get(  # type: ignore
        self,
        key: K,
        default: R | T | _NotSet = NOTSET,
    ) -> (R | T) | (R | None):
        n = self._data.get(key, NOTSET)
        if isinstance(n, _NotSet):
            if default is NOTSET:
                raise KeyError()
            else:
                return default  # type: ignore
        else:
            self._l.remove(n)
            self._l.insert(n)
            return n.value[1]

    def set(self, key: K, value: R) -> None:
        n = self._data.get(key, NOTSET)
        if isinstance(n, _NotSet):
            self._data[key] = n = Node((key, value))
            if len(self._l) >= self._max_size:
                del self._data[self._l._beg.value[0]]  # type: ignore
                self._l.remove(self._l._beg)  # type: ignore
            self._l.insert(n)
        else:
            self._l.remove(n)
            self._l.insert(n)

    def __getitem__(self, key: K) -> R:
        v = self.get(key)
        if isinstance(v, _NotSet) or v is None:
            raise KeyError(key)
        return v

    def __setitem__(self, key: K, item: R) -> None:
        self.set(key, item)

    def __delitem__(self, key: K) -> None:
        n = self._data.get(key, NOTSET)
        if isinstance(n, _NotSet):
            raise KeyError(key)
        self._l.remove(n)
        del self._data[n.value[0]]

    def __iter__(self) -> typing.Generator[K, None, None]:
        for x in self._l.traverse_from_beg():
            yield x.value[0]
        return None

    def __len__(self) -> int:
        return len(self._l)
