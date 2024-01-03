import re
import ssl
from datetime import datetime
from io import StringIO

import aiohttp
import certifi
from bs4 import BeautifulSoup, Tag
from intelhex import IntelHex  # type: ignore
from pydantic import BaseModel


class FwCheckError(Exception):
    pass


sslcontext = ssl.create_default_context(cafile=certifi.where())


async def get_fw(chip_type: int, beta: bool = False, chip_type_t: int = 0) -> bytes:
    # TODO: вопрос chip_type_t - это флаг старого бутлодера?
    fname = "megad-2561{suffix}.hex" if chip_type == 2561 else "megad-328{suffix}.hex"
    fname = fname.format(suffix="-beta" if beta else "")
    prefix = "megad-firmware-2561" if chip_type == 2561 else "megad-firmware"
    print("Downloading firmware... ", end="")
    async with aiohttp.ClientSession() as cl:
        async with cl.request(
            "get",
            f"http://ab-log.ru/files/File/{prefix}/latest/{fname}",
            allow_redirects=True,
            ssl_context=sslcontext,
        ) as req:
            ret = await req.text()

    with StringIO(ret) as f:
        ih = IntelHex(f)
        firmware = ih.tobinstr()
        if not isinstance(firmware, bytes):
            raise TypeError()

    print("Checking firmware... ", end="")

    if (len(firmware) > 28670 and chip_type == 0) or (len(firmware) > 258046 and chip_type == 2561):
        raise FwCheckError("FAULT! Firmware is too large!\n")
    elif len(firmware) < 1000:
        raise FwCheckError("FAULT! Firmware length is zero or file is corrupted!\n")
    elif len(firmware) > 32768 and chip_type == 2561 and chip_type_t == 1:
        raise FwCheckError("FAULT! You have to upgrade bootloader!\n")
    else:
        print("OK\n")

    return firmware


FW_URL = "https://ab-log.ru/smart-house/ethernet/megad-2561-firmware"
PATT_DT = re.compile(r"(\d{2}\.\d{2}\.\d{4})")
PATT_VER = re.compile(r"ver (\d+)\.(\d+) beta(\d+)")
PATT_DESC = re.compile(r'<br>(.*?)<a href="/files/', re.DOTALL)


class FW(BaseModel):
    url: str
    ver: tuple[int, int, int]
    dt: datetime
    desc: str
    eeprom: bool


async def get_fw_list() -> list[FW]:
    async with aiohttp.ClientSession() as cl:
        async with cl.request(
            "get",
            FW_URL,
            allow_redirects=True,
            ssl_context=sslcontext,
        ) as req:
            ret = await req.text()
    d = BeautifulSoup(ret).find("div", class_="cnt")
    if d is None:
        raise ValueError("empty response")
    dd = d.find("ul")
    if not isinstance(dd, Tag):
        raise ValueError("empty response")
    r: list[FW] = []
    for link in dd.find_all("li"):
        if not isinstance(link, Tag):
            continue
        _t = link.find("font", attrs={"color": "#666"})
        if _t is None:
            raise ValueError("no title info")
        t = _t.text
        if m := PATT_DT.search(t):
            dt = datetime.strptime(m.group(1), "%d.%m.%Y")
        else:
            raise ValueError("no date")
        if m := PATT_VER.search(t):
            ver = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        else:
            raise ValueError("no version")
        desc = "\n".join(x for x in link.contents if isinstance(x, str) and len(x) > 4)
        url = link.find("a", href=lambda x: x and x.endswith("-hex.zip"))
        if not isinstance(url, Tag):
            raise ValueError("no fw url")
        eeprom = "EEPROM" in desc
        r.append(
            FW(
                url=url.attrs["href"],
                ver=ver,
                dt=dt,
                desc=desc,
                eeprom=eeprom,
            )
        )
    return r
