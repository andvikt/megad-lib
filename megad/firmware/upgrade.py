import ssl
from io import StringIO

import aiohttp
import certifi
from intelhex import IntelHex  # type: ignore


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
