import re
import ssl
from datetime import datetime, timedelta
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

Version = tuple[int, int, int]


class FW(BaseModel):
    url: str
    ver: Version
    dt: datetime
    desc: str
    eeprom: bool
    read_more_url: str


_last_update: datetime | None = None
_cache_list: list[FW] | None = None
_cache_ttl = timedelta(hours=24)


async def get_fw_list() -> list[FW]:
    global _cache_list, _last_update
    if _cache_list is not None and _last_update is not None and (datetime.now() - _last_update) <= _cache_ttl:
        return _cache_list
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
        read_more_url = ""
        if rm := link.find("a", string="Подробнее"):
            if isinstance(rm, Tag):
                read_more_url = rm.attrs["href"]
        if read_more_url:
            desc += f" [Подробнее](https://ab-log.ru{read_more_url})"
        eeprom = "EEPROM" in desc
        r.append(
            FW(
                url=url.attrs["href"],
                ver=ver,
                dt=dt,
                desc=desc,
                eeprom=eeprom,
                read_more_url=read_more_url,
            )
        )
    r.sort(key=lambda x: x.ver)
    _cache_list = r
    _last_update = datetime.now()
    return r


class FwUpgradeSummary(BaseModel):
    desc_md: str
    need_reset: bool


def get_nearest_index(
    fw_list: list[FW],
    ver: Version,
) -> tuple[bool, int]:
    change = False
    for i, fw in enumerate(fw_list):
        if fw.ver >= ver:
            return change, i
        change = True
    raise KeyError(ver)


def get_upgrade_summary(
    fw_list: list[FW],
    current_version: Version,
    target_version: Version,
    full_desc: bool = False,
) -> FwUpgradeSummary:
    fw_dict = {x.ver: i for i, x in enumerate(fw_list)}
    need_reset = False
    desc: list[str] = []
    if current_version < target_version:
        # up
        _, beg = get_nearest_index(fw_list, current_version)
        end = fw_dict[target_version]
        for fw in fw_list[beg : end + 1]:
            if full_desc:
                desc.append(f"## {fw.dt.strftime('%d.%m.%Y')}: {fw.ver[0]}.{fw.ver[1]} beta{fw.ver[2]}\n\n{fw.desc}")
            else:
                desc.append(fw.desc)
            if fw.eeprom:
                need_reset = True
    elif current_version > target_version:
        beg = fw_dict[target_version]
        _, end = get_nearest_index(fw_list, current_version)
        # desc"# Downgrade\n\n"
        for fw in reversed(fw_list[beg : end + 1]):
            if full_desc:
                desc.append(f"## {fw.dt.strftime('%d.%m.%Y')}: {fw.ver[0]}.{fw.ver[1]} beta{fw.ver[2]}\n\n{fw.desc}")
            else:
                desc.append(fw.desc)
            if fw.eeprom:
                need_reset = True
    desc_md = f"# {'.'.join(map(str, current_version))} -> {'.'.join(map(str, target_version))}\n\n"
    if need_reset:
        desc_md += (
            "# ВНИМАНИЕ! Данное обновление требует обязательного сброса eeprom.\n\n"
            "В процессе обновления будет создана резервная копия, "
            "произведен сброс, затем восстановление из резервной копии после успешного обновления.\n\n"
        )
    desc_md += "## список изменений:\n\n"
    desc_md += "\n".join(desc[::-1])
    return FwUpgradeSummary(
        desc_md=desc_md,
        need_reset=need_reset,
    )
