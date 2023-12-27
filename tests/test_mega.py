from collections.abc import AsyncIterable
from io import StringIO
from time import time

import pytest
import pytest_asyncio
from megad import scan_network_for_megad
from megad.core import MegaD
from megad.scan import Upgrader
from utils import timer


@pytest.mark.asyncio()
async def test_scan() -> None:
    res = await scan_network_for_megad()
    print(res)


@pytest_asyncio.fixture
async def mega() -> AsyncIterable[MegaD]:
    _mega = MegaD(ip="192.168.88.15", password="sec")
    # _mega = MegaD(ip="10.0.0.252", password="sec")
    yield _mega
    # await _mega._client.aclose()
    await _mega.close()


@pytest.mark.asyncio()
async def test_get_config(mega: MegaD) -> None:
    ret = await mega.get_config()
    assert ret.cf1 is not None
    print(mega.json(exclude={"_client"}))
    print(ret)


@pytest.mark.asyncio()
async def test_get_backup(mega: MegaD) -> None:
    with StringIO() as f:
        await mega.backup(f)


@pytest.mark.asyncio()
async def test_restore_backup(mega: MegaD) -> None:
    with open("megad1.cfg") as f:
        await mega.restore(f)


@pytest.mark.asyncio()
async def test_upgrade(mega: MegaD) -> None:
    with StringIO() as f:
        with timer("backup"):
            await mega.backup(f)
        await mega.upgrade(True, f)


@pytest.mark.asyncio()
async def test_set_ip(mega: MegaD) -> None:
    upgrader = Upgrader("192.168.88.15", mega.password)
    async with upgrader.send_ctx():
        await upgrader.set_ip(mega.ip, old_ip="192.168.88.15")
