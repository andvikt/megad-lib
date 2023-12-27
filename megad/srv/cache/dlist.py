import dataclasses
import typing

R = typing.TypeVar("R")
K = typing.TypeVar("K")


@dataclasses.dataclass(slots=True)
class Node(typing.Generic[R]):
    value: R
    prev: typing.Union["Node[R]", None] = None
    next: typing.Union["Node[R]", None] = None


class DList(typing.Generic[R]):
    def __init__(self) -> None:
        self._size = 0
        self._beg: Node[R] | None = None
        self._end: Node[R] | None = None

    def insert(self, n: Node[R], after: Node[R] = None) -> None:
        self._size += 1
        after = after or self._end
        if self._beg is None:
            self._beg = self._end = n
        elif after:
            n.prev = after
            n.next = after.next
            if after.next:
                after.next.prev = n
            after.next = n
            if after is self._end:
                self._end = n
        return

    def traverse_from_beg(self) -> typing.Generator[Node[R], None, None]:
        n = self._beg
        if n is None:
            return None
        yield n
        while n.next:
            n = n.next
            yield n

    def remove(self, n: Node[R]) -> None:
        self._size -= 1
        if n is self._beg:
            self._beg = n.next
        if n is self._end:
            self._end = n.prev
        if n.next:
            n.next.prev = n.prev
        if n.prev:
            n.prev.next = n.next
        n.prev = None
        n.next = None

    def move_to_end(self, n: Node[R]) -> None:
        self.remove(n)
        self.insert(n)

    def __getitem__(self, key: int) -> Node[R]:
        if key < 0:
            key = self._size + key
        if key >= self._size or key < 0:
            raise IndexError()
        n = self._beg
        if not n:
            raise IndexError()
        i = 0
        while n.next and i < key:
            n = n.next
            i += 1
        return n

    def __len__(self) -> int:
        return self._size
