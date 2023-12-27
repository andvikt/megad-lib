import typing
from collections.abc import Awaitable, Callable, Iterable
from datetime import datetime
from typing import Optional, TypeVar, cast

from sqlalchemy import ColumnExpressionArgument, func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    attributes,
    mapped_column,
    selectinload,
)

from .engine import _ctx

T = typing.TypeVar("T", bound="BaseMixin")
Tk = typing.TypeVar("Tk")
Tc = typing.TypeVar(
    "Tc",
    bound="Base",
)
P = typing.ParamSpec("P")


class CreatedMixin(MappedAsDataclass):
    created_dttm: Mapped[datetime] = mapped_column(insert_default=func.current_timestamp(), init=False)


class Base(MappedAsDataclass, DeclarativeBase):
    pass


R = TypeVar("R", bound=Base)


class _Upsert:
    def __get__(self, inst: R | None, cls: Callable[P, R]) -> Callable[P, Awaitable[R]]:
        return upsert(cls)


class BaseMixin(MappedAsDataclass):
    id: Mapped[int] = mapped_column(init=False, primary_key=True)  # noqa: A003

    @property
    def id_32(self) -> bytes:
        return self.id.to_bytes(4, "little", signed=False)

    @classmethod
    async def must_get(
        cls: type[T],
        session: AsyncSession,
        id: int,  # noqa: A002
        include: list[attributes.QueryableAttribute[typing.Any]] | None = None,
        raise_: typing.Callable[[], Exception] = KeyError,
    ) -> T:
        if r := await cls.get(session, id, include):
            return r
        else:
            raise raise_()

    @classmethod
    async def get(
        cls: type[T],
        session: AsyncSession,
        id: int,  # noqa: A002
        include: list[attributes.QueryableAttribute[typing.Any]] | None = None,
    ) -> T | None:
        options = []
        if include:
            options.extend([selectinload(x) for x in include])
        ret = await session.get(cls, id, options=options)
        return ret

    @classmethod
    async def query(
        cls: type[T],
        session: AsyncSession,
        where: ColumnExpressionArgument[bool] | None = None,
        order_by: ColumnExpressionArgument[typing.Any] | None = None,
        include: list[attributes.QueryableAttribute[typing.Any]] | None = None,
    ) -> typing.AsyncGenerator[T, None]:
        stmt = select(cls)
        if where is not None:
            stmt = stmt.where(where)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        options = []
        if include:
            options.extend([selectinload(x) for x in include])
        if options:
            stmt = stmt.options(*options)
        result = await session.stream(stmt)
        async for p in result.scalars():
            yield p

    @classmethod
    async def search_one(
        cls: type[T],
        session: AsyncSession,
        where: ColumnExpressionArgument[bool] | None = None,
    ) -> T:
        stmt = select(cls)
        if where is not None:
            stmt = stmt.where(where)
        result = await session.scalars(stmt)
        return result.one()

    upsert = _Upsert()


async def db_add(session: AsyncSession, obj: T) -> T:
    """Добавляет объект используя returning, возвращает новый объект с заполненными id

    Args:
        session (AsyncSession): сессия
        obj (T): объект

    Returns:
        T: объект
    """
    session.add(obj)
    await session.flush([obj])
    return obj


def _upsert(
    t: Callable[P, R],
    index_elements: Optional[Iterable[str]] = None,
    returning: bool = True,
) -> Callable[P, Awaitable[R | None]]:
    async def add(*args: P.args, **kwargs: P.kwargs) -> R | None:
        try:
            sess = _ctx.get()
        except LookupError as exc:
            raise RuntimeError(f"{t}.upsert is called outside session context") from exc

        stmt = (
            insert(t)  # type: ignore
            .values(kwargs)
            .on_conflict_do_update(
                set_=kwargs,
                index_elements=index_elements,
            )
        )
        if returning:
            stmt = stmt.returning(t)  # type: ignore
        if r := await sess.scalar(
            stmt,
            execution_options={"populate_existing": True} if returning else {},
        ):
            return cast(R, r)
        return None

    return add


def upsert(
    t: Callable[P, R],
    index_elements: Optional[Iterable[str]] = None,
) -> Callable[P, Awaitable[R]]:
    return cast(Callable[P, Awaitable[R]], _upsert(t, index_elements))
