from functools import cached_property
from typing import IO, Any

from aiohttp import TCPConnector
from aiohttp.client import ClientSession
from pydantic import BaseModel, Field

from utils import timer

from .backup import get_backup
from .firmware.upgrade import get_fw
from .parsers import Config as Cfg
from .parsers import get_parser
from .scan import Upgrader


def _clean_nones(d: dict[str, Any]) -> dict[str, Any]:
    return {n: v for n, v in d.items() if v is not None}


class MegaD(
    BaseModel,
):
    class Config:
        keep_untouched = (cached_property,)
        orm_mode = True
        arbitrary_types_allowed = True

    ip: str
    password: str = "sec"
    name: str = "mega"
    mid: str = "mega"
    new_naming: bool = True

    cfg: Cfg = Field(default_factory=lambda: Cfg(cf1=None, cf2=None))

    @cached_property
    def _client(self) -> ClientSession:
        return ClientSession(
            base_url=f"http://{self.ip}",
            connector=TCPConnector(limit=1),
        )

    async def close(self) -> None:
        await self._client.close()

    async def get(
        self,
        url: str = None,
        pt: int | str | None = None,
        cmd: str | None = None,
        cf: int = None,
        timeout: int | None = None,
        **kwargs: int | str,
    ) -> str:
        if url:
            assert pt is None
            assert cmd is None
            async with self._client.get(
                f"/{self.password}{url}",
                timeout=timeout,
            ) as req:
                return await req.text(encoding="iso-8859-5")
        async with self._client.get(
            f"/{self.password}/",
            params=_clean_nones({"pt": pt, "cmd": cmd, "cf": cf} | kwargs),
            timeout=timeout,
        ) as req:
            return await req.text(encoding="iso-8859-5")

    async def get_config(self, only_first: bool = False) -> Cfg:
        cfg = self.cfg
        while cfg._next_paths:
            for p in cfg._next_paths.copy():
                if parser := get_parser(p):
                    cfg.add_parsed(p)
                    await parser(self, p, await self.get(f"{p}", timeout=1))
                else:
                    cfg.add_skipped(p)
            if only_first:
                break
        return cfg

    async def backup(self, fh: IO[str]) -> None:
        await get_backup(self, fh)

    async def restore(self, fh: IO[str]) -> None:
        for line in fh:
            url = f"/{self.password}/?{line.strip()}"
            async with self._client.get(url) as req:
                assert req.status == 200, req.status

    async def upgrade(
        self,
        reset_eeprom: bool = False,
        backup: IO[str] | None = None,
        fw: bytes | None = None,
    ) -> None:
        if reset_eeprom and not backup:
            raise ValueError("can earse eeprom only with a backup")
        async with Upgrader(self.ip, self.password) as upgrader:
            if fw is None:
                if upgrader.chip_type:
                    with timer("get_fw"):
                        fw = await get_fw(upgrader.chip_type, beta=False)
                else:
                    raise ValueError(f"{upgrader.chip_type=}")
            with timer("earse fw"):
                await upgrader.earse_fw()
            if reset_eeprom:
                with timer("earse eeprom"):
                    await upgrader.earse_eeprom()
            with timer("write fw"):
                await upgrader.write_fw(fw)
            if reset_eeprom:
                with timer("restore"):
                    await upgrader.restart()
                    await upgrader.set_ip(self.ip)
                    await self.restore(backup)  # type: ignore
