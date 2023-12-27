from __future__ import annotations

import contextlib
import typing
from contextvars import ContextVar
from pathlib import Path

import orjson
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command, config

# from ..config import get_settings

engine: AsyncEngine | None = None
session_maker: async_sessionmaker[AsyncSession] | None = None
CFG_ROOT = Path(__file__).parent.parent
alembic_config = config.Config(
    CFG_ROOT / "alembic.ini",
    config_args={
        # "prepend_sys_path": str(CFG_ROOT),
        # "alembic": {
        "script_location": str(CFG_ROOT / "alembic"),
        # }
    },
)


def orjson_serializer(obj: typing.Any) -> str:
    """
    Note that `orjson.dumps()` return byte array, while sqlalchemy expects string, thus `decode()` call.
    """
    return orjson.dumps(obj, option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_NAIVE_UTC).decode()


@contextlib.asynccontextmanager
async def db_life(
    uri: str,
    migrate: bool = False,
    drop_all: bool = False,
    is_test: bool = False,
) -> typing.AsyncIterator[AsyncEngine]:
    global session_maker, engine
    from .base import Base

    engine = create_async_engine(
        uri,
        json_serializer=orjson_serializer,
        json_deserializer=orjson.loads,
        pool_pre_ping=True,
        # echo=True,
    )
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        if drop_all:
            await conn.run_sync(Base.metadata.drop_all)

    async with engine.begin() as conn:
        if migrate and drop_all:
            await conn.run_sync(Base.metadata.create_all)
        elif migrate:
            await conn.run_sync(run_upgrade, alembic_config)
    try:
        yield engine

        if is_test:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
    finally:
        await engine.dispose()


async def _get_db(autocommit: bool = True) -> typing.AsyncIterator[AsyncSession]:
    if session_maker is None:
        raise ValueError("database is not initialised")
    sess = session_maker()
    async with sess.begin():
        reset = _ctx.set(sess)
        try:
            yield sess
        finally:
            _ctx.reset(reset)


_ctx = ContextVar[AsyncSession]("_ctx")
session_ctx = contextlib.asynccontextmanager(_get_db)


def run_upgrade(connection: Connection, cfg: config.Config) -> None:
    cfg.attributes["connection"] = connection
    command.upgrade(cfg, "head")


def run_rev(connection: Connection, cfg: config.Config) -> None:
    cfg.attributes["connection"] = connection
    # command.stamp(cfg, "head")
    command.revision(
        cfg,
        message=".",
        autogenerate=True,
    )


async def run_async_upgrade(async_engine: AsyncEngine) -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(run_upgrade, alembic_config)


async def async_rev(uri: str) -> None:
    async with db_life(uri) as engine:
        async with engine.begin() as conn:
            await conn.run_sync(run_rev, alembic_config)
