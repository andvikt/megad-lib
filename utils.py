from contextlib import contextmanager
from time import time
from typing import Any, Generator


@contextmanager
def timer(name: str) -> Generator[None, Any, None]:
    beg = time()
    try:
        yield
    finally:
        print(f"{name} time {time() - beg: 0.1f}")
