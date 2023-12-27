from typing import Protocol

from bs4 import BeautifulSoup


class ObjectData(Protocol):
    @property
    def bs(self) -> BeautifulSoup:
        ...
