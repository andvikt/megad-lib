import ast
import re
import typing

from bs4 import BeautifulSoup, Tag

from megad.parsers.config import Cf1, Cf2
from megad.parsers.const import PATT_FW, PATT_VAR_B, PATT_VAR_C

from .base import BaseObject
from .tools import parser

if typing.TYPE_CHECKING:
    from ..core import MegaD


@parser(re.compile(r"^\/\?pt=\d{1,2}$"))
async def parse_pt(mega: "MegaD", path: str, data: str) -> None:
    o = BaseObject(html=data, mega=mega)
    cfg = mega.cfg
    for e in o.bs.find_all("a"):
        if isinstance(e, Tag):
            href = e.attrs["href"]
            cfg.add_next(href)
    async for d in o.get_devices():
        cfg.objects.append(d)


@parser("/")
async def parse_main(mega: "MegaD", path: str, data: str) -> None:
    tree = BeautifulSoup(data)
    cfg = mega.cfg
    if m := PATT_FW.search(data):
        cfg.version = m.group(1)
    else:
        raise ValueError("version not found")
    for e in tree.find_all("a"):
        if isinstance(e, Tag):
            href = e.attrs["href"]
            cfg.add_next(href)
    if m := PATT_VAR_B.search(data):
        b: list[tuple[int, str, int, str]] = ast.literal_eval(m.group(1))
        for o in b:
            cfg.add_next(f"/?pt={o[0]}")
            cfg.add_next(f"/?pt={o[2]}")
    if m := PATT_VAR_C.search(data):
        c: list[tuple[int, str]] = ast.literal_eval(m.group(1))
        for ll in c:
            cfg.add_next(f"/?pt={ll[0]}")
    pass


@parser(re.compile(r"^\/\?cf=3$"))
async def parse_cf3(mega: "MegaD", path: str, data: str) -> None:
    return


@parser(re.compile(r"^\/\?cf=1$"))
async def parse_cf1(mega: "MegaD", path: str, data: str) -> None:
    mega.cfg.cf1 = cf = Cf1(html=data)
    for e in cf.bs.find_all("a"):
        if isinstance(e, Tag):
            href = e.attrs["href"]
            mega.cfg.add_next(href)


@parser(re.compile(r"^\/\?cf=2$"))
async def parse_cf2(mega: "MegaD", path: str, data: str) -> None:
    mega.cfg.cf2 = Cf2(html=data)


@parser(re.compile(r"^\/\?cf=\d$"))
async def parse_cf(mega: "MegaD", path: str, data: str) -> None:
    tree = BeautifulSoup(data)
    cfg = mega.cfg
    for e in tree.find_all("a"):
        if isinstance(e, Tag):
            href = e.attrs["href"]
            cfg.add_next(href)
    pass
