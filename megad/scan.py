import asyncio
import socket
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Self

import aiohttp


class MegaUDPCommand(int, Enum):
    GET_CHIP = 0x00
    WRITE_FIRMWARE = 0x01
    EARSE_FW = 0x02
    RESTART = 0x03
    SET_IP = 0x04
    EARSE_EEPROM = 0x09
    SCAN = 0x0C


PACK_CHECK = bytes([0xDA, 0xCA])


class _MegaScanProtocol(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        super().__init__()
        self.found_addrs = list[str]()

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:  # type: ignore
        self.transport = transport
        sock = transport.get_extra_info("socket")
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.broadcast()

    def datagram_received(self, data: bytes, addr: tuple[str | Any, int]) -> None:
        self.found_addrs.append(addr[0])

    def broadcast(self) -> None:
        self.transport.sendto(b"\xAA\x00\x0C\xDA\xCA", ("<broadcast>", 52000))


class MegaUpgradeProtocol(asyncio.DatagramProtocol):
    def __init__(
        self,
        check_data: bytes = b"",
    ) -> None:
        super().__init__()
        self.que = asyncio.Queue[bytes]()
        self.started = asyncio.Event()
        self.check_data = check_data

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:  # type: ignore
        self.transport = transport
        sock = transport.get_extra_info("socket")
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.started.set()

    def datagram_received(self, data: bytes, addr: tuple[str | Any, int]) -> None:
        self.que.put_nowait(data)

    async def send_command(
        self,
        command: MegaUDPCommand,
        payload: bytes = b"",
        msg_id: int = 0,
        timeout: int = 1,
        control_header: bytes | None = None,
    ) -> bytes:
        header = bytes([0xAA, msg_id % 256, command])
        self.transport.sendto(header + self.check_data + payload, ("<broadcast>", 52000))
        try:
            ret = await asyncio.wait_for(self.que.get(), timeout)
        except TimeoutError:
            if not self.check_data:
                self.check_data = PACK_CHECK
            else:
                self.check_data = b""
            self.transport.sendto(header + self.check_data + payload, ("<broadcast>", 52000))
            ret = await asyncio.wait_for(self.que.get(), timeout)
        if not control_header:
            assert ret[:2] == header[:2], f"bad answer {ret[:2]=}!={header[:2]=}"
        else:
            assert ret[: len(control_header)] == control_header, f"bad answer {ret[:2]=}!={control_header[:2]=}"
        return ret


async def scan_network_for_megad(timeout: int = 1) -> list[str]:
    """scan network for mega devices

    Args:
        timeout (int, optional): wait for this amount of seconds. Defaults to 1.

    Returns:
        list[str]: list of found ip addresses
    """
    trasnport, some = await asyncio.get_event_loop().create_datagram_endpoint(
        _MegaScanProtocol,
        local_addr=("0.0.0.0", 42000),
    )
    await asyncio.sleep(timeout)
    trasnport.close()
    return some.found_addrs


@dataclass
class Upgrader:
    ip: str
    password: str

    chip_type: int | None = None
    chip_type_t: int | None = None

    exit_stack: AsyncExitStack = field(default_factory=AsyncExitStack, init=False)
    proto: MegaUpgradeProtocol | None = field(default=None, init=False)
    _restarted: bool = False

    async def _send(
        self,
        cmd: MegaUDPCommand,
        payload: bytes = b"",
        msg_id: int = 0,
        timeout: int = 10,
        control_header: bytes | None = None,
    ) -> bytes:
        if self.proto is None:
            raise ValueError("context not started")
        return await self.proto.send_command(cmd, payload, msg_id, timeout, control_header)

    async def __aenter__(self) -> Self:
        self.proto = await self.exit_stack.enter_async_context(self.upgrade_ctx())
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:  # type:ignore
        await self.exit_stack.aclose()
        return None

    @asynccontextmanager
    async def send_ctx(self) -> AsyncIterator[MegaUpgradeProtocol]:
        trasnport, proto = await asyncio.get_event_loop().create_datagram_endpoint(
            MegaUpgradeProtocol,
            local_addr=("0.0.0.0", 42000),
        )
        self.proto = proto
        try:
            await proto.started.wait()
            await asyncio.sleep(1)
            yield proto
        finally:
            trasnport.close()
            self.proto = None

    @asynccontextmanager
    async def upgrade_ctx(self) -> AsyncIterator[MegaUpgradeProtocol]:
        """
        Здесь контроллер переходит в режим обновления, используется контекст, чтобы при любых ошибках корректно выйти из
        режима обновления.
        """
        trasnport, proto = await asyncio.get_event_loop().create_datagram_endpoint(
            MegaUpgradeProtocol,
            local_addr=("0.0.0.0", 42000),
        )
        self.proto = proto
        with suppress(aiohttp.ClientResponseError):
            async with aiohttp.request(
                "get",
                f"http://{self.ip}/{self.password}/?fwup=1",
                raise_for_status=False,
                timeout=aiohttp.ClientTimeout(total=5),
            ):
                pass
        try:
            await proto.started.wait()
            await asyncio.sleep(1)
            pkt = await self._send(MegaUDPCommand.GET_CHIP)
            self._restarted = False
            try:
                self.chip_type, self.chip_type_t = self.get_chip_type(pkt)
                yield proto
            finally:
                if not self._restarted:
                    await self.restart()
        finally:
            trasnport.close()
            self.proto = None

    async def earse_fw(self) -> None:
        """Удаление текущей прошивки"""
        await self._send(MegaUDPCommand.EARSE_FW, timeout=20)

    async def earse_eeprom(self) -> None:
        """Удаление текущей прошивки"""
        await self._send(MegaUDPCommand.EARSE_EEPROM, timeout=30)
        if self.chip_type == 2561:
            await self._send(MegaUDPCommand.EARSE_EEPROM, msg_id=1, timeout=30)

    async def restart(self) -> None:
        """Перезагрузка"""
        await self._send(MegaUDPCommand.RESTART)
        self._restarted = True

    async def write_fw(self, firmware: bytes) -> None:
        """Запись новой прошивки

        Args:
            firmware (bytes): прошивка в байтах
        """
        block_size = 256 if self.chip_type == 2561 else 128
        for msg_id, i in enumerate(range(0, len(firmware) + 1, block_size)):
            payload = firmware[i : i + block_size]
            if not payload:
                break
            await self._send(MegaUDPCommand.WRITE_FIRMWARE, payload, msg_id=msg_id)

    async def set_ip(self, new_ip: str, old_ip: str = "192.168.0.14", password: str = "sec") -> None:
        """Установка IP"""
        payload = password.encode()
        payload = payload.ljust(5, b"\0")
        payload += bytes([int(x) for x in old_ip.split(".") + new_ip.split(".")])
        try:
            await self._send(
                MegaUDPCommand.SET_IP,
                payload,
                control_header=bytes([0xAA, 0x01]),
            )
        except (AssertionError, TimeoutError):
            payload = bytes([0xDA, 0xCA]) + payload
            await self._send(
                MegaUDPCommand.SET_IP,
                payload,
                control_header=bytes([0xAA, 0x01]),
            )

    @staticmethod
    def get_chip_type(pkt: bytes, check_data: bytes = b"") -> tuple[int, int]:
        chip_type_t = 0
        if pkt[2] == 0x99 or pkt[2] == 0x9A:
            if not check_data:
                print(" (new bootloader)")
            if pkt[2] == 0x99:
                print("WARNING! Please upgrade bootloader!\n")
                chip_type_t = 1
            chip_type = 2561
        else:
            chip_type = 328
            print(" (chip type: atmega328)\n")
        return chip_type, chip_type_t
