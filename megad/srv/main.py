import asyncio
from contextlib import suppress
from typing import Generic, Optional

from aiohttp import ClientResponseError, web
from cashews import cache
from pydantic import BaseModel
from sqlalchemy import and_, asc, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from megad.parsers.base import BaseObject
from megad.parsers.enums import EnumPty

from ..config import config
from ..core import MegaD
from ..db import objects as db
from ..db.engine import session_ctx
from ..scan import scan_network_for_megad
from .errors import BadPasswordError, NoSuchController, ParsingError, VesionNotFoundError
from .router import Path, T, err, router

# cache = MemoryCache[Any]()


class GenericItems(BaseModel, Generic[T]):
    items: list[T]


class Controller(BaseModel, orm_mode=True):
    id: int
    ip: str
    active: bool
    name: Optional[str]
    mid: Optional[str]
    password: Optional[str]
    version: Optional[str]
    status: db.EnumStatus
    device_cnt: Optional[int]


async def _get_list_controllers(sess: AsyncSession) -> GenericItems[Controller]:
    db_objs = await sess.scalars(select(db.Controller).order_by(asc(db.Controller.created_dttm)))

    return GenericItems(items=[Controller.from_orm(x) for x in db_objs.all()])


@router.post("/list")
async def get_list() -> GenericItems[Controller]:
    async with session_ctx() as sess:
        return await _get_list_controllers(sess)


@router.post("/scan")
async def scan() -> GenericItems[Controller]:
    res = [MegaD(ip=x) for x in await scan_network_for_megad()]
    await asyncio.gather(*(m.get_config(only_first=True) for m in res))

    async with session_ctx():
        return GenericItems(
            items=[
                Controller.from_orm(
                    await db.upsert_controller(
                        ip=x.ip,
                        password=x.password,
                        version=x.cfg.version,
                    )
                )
                for x in res
            ]
        )


class ResponseConfig(BaseModel):
    srv_ip: str


@router.get("/config")
async def get_config() -> ResponseConfig:
    return ResponseConfig(srv_ip=config.interface)


class RequestNewController(BaseModel):
    ip: str
    name: str
    mid: str
    password: str
    srv_ip: str


async def _scan_controller(c: MegaD) -> Controller:
    try:
        await c.get_config()
    except ClientResponseError as exc:
        if exc.status == 401:
            raise BadPasswordError() from exc
        raise ParsingError() from exc
    except Exception as exc:
        raise ParsingError() from exc
    if c.cfg.version is None:
        raise VesionNotFoundError()

    db_controller = await db.upsert_controller(
        ip=c.ip,
        password=c.password,
        mid=c.mid,
        version=c.cfg.version,
        name=c.name,
        status=db.EnumStatus.ONLINE,
        config_data=c.cfg.dict(),
    )

    for dev in c.cfg.objects:
        if dev.port is None:
            continue
        await db.upsert_device(
            controller_id=db_controller.id,
            unique_id=dev.unique_id,
            active=False,
            config_data=dev.to_json(),
            port=dev.port,
        )

    ret = Controller.from_orm(db_controller)
    ret.device_cnt = len(c.cfg.objects)
    ret.active = True
    return ret


@router.post("/add")
async def add_controller(r: RequestNewController) -> Controller:
    c = MegaD(ip=r.ip, password=r.password, mid=r.mid, name=r.name)
    async with session_ctx() as sess:
        with suppress(NoResultFound):
            await db.Controller.search_one(sess, and_(db.Controller.ip == r.ip, db.Controller.active.is_(True)))
            raise err(web.HTTPConflict, text=f"{r.ip=} is already added")
        return await _scan_controller(c)


@router.post("/rescan/{mega_id}")
async def rescan(mega_id: Path[int]) -> None:
    async with session_ctx() as sess:
        db_c = await db.Controller.get(sess, mega_id)
        if db_c is None:
            raise NoSuchController()
        mega = MegaD.from_orm(db_c)
        await _scan_controller(mega)
    await cache.delete_tags(f"list:{mega_id}")
    return None


class ResponseDevice(BaseModel, orm_mode=True):
    id: int
    port: Optional[int]
    config_data: Optional[str]
    entity_id: Optional[str]
    friendly_name: Optional[str]
    platform: Optional[str]
    title: Optional[str]
    pty: Optional[EnumPty | None]


# @cache.cached("list:{mega_id}")


@router.get("/list/{mega_id}")
@cache("1h", key="list:{mega_id}", tags=["list:{mega_id}"])  # type:ignore
async def list_devices(mega_id: Path[int]) -> GenericItems[ResponseDevice]:
    async with session_ctx(False) as sess:
        db_c = await db.Controller.get(sess, mega_id)
        mega = MegaD.from_orm(db_c)
        ret = await sess.scalars(
            select(db.Device).where(db.Device.controller_id == mega_id).order_by(db.Device.port, db.Device.unique_id)
        )
        return GenericItems(
            items=[
                ResponseDevice.from_orm(
                    BaseObject.from_json(
                        mega,
                        d.config_data,
                        id_=d.id,
                    )
                )
                for d in ret.all()
            ]
        )
