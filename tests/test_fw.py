import pytest
from megad.firmware.upgrade import get_fw, get_fw_list
from megad.scan import Upgrader


@pytest.mark.asyncio()
async def test_get_fw() -> None:
    await get_fw(2561)


# def test_get_chip_type():
#     options = Options(
#         ip="192.168.88.15",
#         password="sec",
#         broadcast_ip="<broadcast>",
#     )
#     with upgrade_ctx(options) as sock:
#         chip_type, chip_type_t = get_chip_type(options, sock)
#     assert chip_type == 2561
#     assert chip_type_t == 0


@pytest.mark.asyncio()
async def test_fw_a() -> None:
    async with Upgrader("192.168.88.15", "sec") as upgrader:
        fw = await get_fw(upgrader.chip_type or 2561, beta=False)
        await upgrader.earse_fw()
        await upgrader.write_fw(fw)


@pytest.mark.asyncio()
async def test_list_fw() -> None:
    fw_list = await get_fw_list()
    print(fw_list)
