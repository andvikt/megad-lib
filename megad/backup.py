import asyncio
import re
import typing
from contextlib import asynccontextmanager

from bs4 import BeautifulSoup

from megad.parsers.config import Cf1

if typing.TYPE_CHECKING:
    from megad.core import MegaD


def get_ports_cnt(page: str) -> int:
    if "IN/OUT" in page:
        if "[44," in page:
            return 45
        else:
            return 37
    elif m := re.search(r".*\?pt=(\d+).*", page):
        return int(m.group(1))
    raise NotImplementedError()


@asynccontextmanager
async def preset_ctx(mega: "MegaD", fh: typing.IO[str]) -> typing.AsyncIterator[None]:
    """временное выключение wdog на время сохранения"""
    cf1 = Cf1(html=await mega.get("/?cf=1"))
    if cf1.watch_dog is not None:
        await mega.get("/?cmd=s")
        await mega.get("/?cf=1&pr=0")
        await asyncio.sleep(1)
        yield
        # перезаписываем значение pr, тк оно ранее было установлено в 0
        fh.write(f"cf=1&pr={cf1.watch_dog}\n")
        await mega.get("/?cmd=s")
        await mega.get(f"/?cf=1&pr={cf1.watch_dog}")
        await asyncio.sleep(1)
    else:
        yield


PAGES = [
    "cf=1",
    "cf=2",
    "cf=6",
    "cf=7",
    "cf=8",
    "cf=9",
]


def _input(name: str, value: typing.Any, inp: typing.Any, port_num: int) -> tuple[str, int]:
    url = ""
    if inp.get("type") == "checkbox":
        value = 1 if inp.has_attr("checked") else ""
    else:
        value = inp.get("value")

    if name == "sl" and not value:
        pass
    elif name == "eth" or name == "emt":
        url += f"{name}={value}&"
    else:
        value = str(value or "").replace("&", "%26")
        url += f"{name}={value}&"

    if name == "pn":
        port_num = int(value)
    return url, port_num


async def _back_page(mega: "MegaD", fh: typing.IO[str], page_param: str, i: int, reboot_flag: int) -> None:
    port_num = 0
    port_type = 0
    port_dev = 0

    page = await mega.get(f"/?{page_param}")
    page = page.replace("<<", "<")

    soup = BeautifulSoup(page)
    url = ""

    for inp in soup.find_all("input"):
        if inp.get("type") == "submit":
            continue
        name = inp.get("name")
        if name == "pt" or name == "pwm":
            continue
        value = inp.get("value")
        url, port_num = _input(name, value, inp, port_num)

    for elem in soup.find_all("select"):
        name = elem.get("name")
        options = elem.find_all("option")
        sel_flag = 0

        for opt in options:
            if not opt.has_attr("selected"):
                continue
            value = opt.get("value")
            url += f"{name}={value}&"
            sel_flag = 1

        if sel_flag == 0 and name == "m":
            url += "m=3&"

        if name == "pty":
            port_type = int(value or "255")
        elif name == "d":
            port_dev = int(value)

        if port_type == 4 and (port_dev == 20 or port_dev == 21):
            for j in range(16):
                PAGES.append(f"pt={port_num}&ext={j}")

    url = re.sub(r"&$", "", url)

    if (not url.startswith("cf=1&") and i < len(PAGES) - 1 and i != reboot_flag) or url.startswith("cf=10&"):
        url += "&nr=1"

    fh.write(f"{url}\n")


async def get_backup(mega: "MegaD", fh: typing.IO[str]) -> None:
    page = await mega.get("")

    ports = get_ports_cnt(page)

    for i in range(ports + 1):
        PAGES.append(f"pt={i}")

    for i in range(10):
        PAGES.append(f"cf=10&prn={i}")

    len(PAGES) - 1

    for i, page_param in enumerate(PAGES):
        await _back_page(
            mega,
            fh,
            page_param,
            i,
            reboot_flag=len(PAGES) - 1,
        )

    return None
