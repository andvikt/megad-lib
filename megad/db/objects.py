from enum import Enum
from functools import cached_property
from typing import Any, Optional

from sqlalchemy import JSON, ForeignKey, Index, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from megad.core import MegaD
from megad.parsers.base import BaseObject
from megad.parsers.config import Config

from .base import Base, BaseMixin, CreatedMixin, upsert


class EnumStatus(int, Enum):
    WAIT_CONFIG = 0
    ONLINE = 1
    OFFLINE = 2


class Controller(Base, BaseMixin, CreatedMixin):
    __tablename__ = "controllers"
    ip: Mapped[str] = mapped_column(index=True, unique=True)
    version: Mapped[str]
    name: Mapped[Optional[str]] = mapped_column(default=None)
    mid: Mapped[Optional[str]] = mapped_column(default=None, index=True)
    config_data: Mapped[Optional[dict[str, Any]]] = mapped_column(type_=JSON, default=None)
    password: Mapped[Optional[str]] = mapped_column(default=None)
    active: Mapped[bool] = mapped_column(default=False)
    status: Mapped[EnumStatus] = mapped_column(
        default=EnumStatus.WAIT_CONFIG,
        type_=SmallInteger,
        server_default="0",
    )
    devices: Mapped[list["Device"]] = relationship(default_factory=list)
    new_naming: Mapped[bool] = mapped_column(default=True)

    @cached_property
    def cfg(self) -> Config | None:
        if self.config_data:
            return Config.parse_obj(self.config_data)
        return None

    # __table_args__ = (UniqueConstraint(ip, mid, name="uix_cont_1"),)


upsert_controller = upsert(
    Controller,
    [
        "ip",
    ],
)


class Device(Base, BaseMixin, CreatedMixin):
    __tablename__ = "devices"
    controller_id: Mapped[int] = mapped_column(ForeignKey("controllers.id"), index=True)
    unique_id: Mapped[str]
    active: Mapped[bool]
    config_data: Mapped[bytes]
    port: Mapped[int]

    __table_args__ = (Index("devices_idx", "controller_id", "unique_id", unique=True),)

    def device(self, mega: MegaD) -> BaseObject:
        return BaseObject.from_json(mega, self.config_data)


upsert_device = upsert(Device, ["controller_id", "unique_id"])
