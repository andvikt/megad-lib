import asyncio
import typing
from collections.abc import AsyncIterable, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, ClassVar, Concatenate, Optional, ParamSpec, TypeAlias, TypeVar, Union
from urllib.parse import parse_qsl, urlparse

import orjson
from bs4 import BeautifulSoup, Tag

from .cache import cached_property
from .const import PATT_DS2413_LIST
from .param_desc import ParamDesc

if typing.TYPE_CHECKING:
    from ..core import MegaD
    from .config import Customization


from .enums import EnumDsenDevice, EnumI2CGroup, EnumI2CMode, EnumOutMode, EnumPty
from .i2c_sensors import EnumI2CSensorDevice
from .tools import T_, BaseObjectMeta, asdict
from .units import SensorDeviceClass

if typing.TYPE_CHECKING:
    from ..core import MegaD


P = ParamSpec("P")
T_co = TypeVar("T_co", bound="BaseObject", covariant=True)
Creator: TypeAlias = Callable[Concatenate[str, "MegaD", P], T_co]


@dataclass
class BaseObject(metaclass=BaseObjectMeta):
    html: str
    mega: "MegaD"

    update_callback: Callable[[], Awaitable[None]] | None = None
    id: Optional[int] = None

    port = ParamDesc("pn", int)
    pty = ParamDesc("pty", EnumPty)
    title = ParamDesc("emt", str)

    _def_platform: ClassVar[str | None] = None

    def __post_init__(self) -> None:
        self._cache: dict[str, Any] = {}

    @cached_property
    def bs(self) -> BeautifulSoup:
        return BeautifulSoup(self.html)

    @cached_property
    def id_suffix(self) -> str | None:
        """Суффикс, который может переопределяться у наследователей. Суффикс участвует в формировании unique_id."""
        return None

    @property
    def unique_id(self) -> str:
        """Уникальный идентификатор. Состоит из названия контроллера, номера порта и суфикса"""
        if not hasattr(self, "ext"):
            # здесь мы следуем логике ранней версии, чтобы не потерять обратную совместимость
            names = [self.mega.mid, self.port]
            if self.id_suffix:
                names.append(self.id_suffix)
            return "_".join(map(str, names))
        elif self.mega.new_naming:
            return f"{self.mega.mid}_{self.port:02d}e{self.ext:02d}"
        else:
            return f"{self.mega.mid}_{self.port}e{self.ext}"

    @property
    def customization(self) -> Union["Customization", None]:
        """У каждого устройства может быть определена кастомизация"""
        if c := self.mega.cfg.customization.get(self.unique_id):
            return c
        else:
            return None

    @property
    def entity_id(self) -> str:
        """entity_id для HA"""
        if self.customization and self.customization.entity_id:
            return self.customization.entity_id
        else:
            if not hasattr(self, "ext"):
                names = [self.mega.mid, f"{self.port:02d}" if self.mega.new_naming else self.port]
                if self.id_suffix:
                    names.append(self.id_suffix)
                return "_".join(map(str, names))
            elif self.mega.new_naming:
                return f"{self.mega.mid}_{self.port:02d}e{self.ext:02d}"
            else:
                return f"{self.mega.mid}_{self.port}e{self.ext}"

    @property
    def friendly_name(self) -> str:
        """friendly_name для HA"""
        if self.customization and self.customization.name:
            return self.customization.name
        else:
            return self.entity_id

    @property
    def platform(self) -> str | None:
        if self.customization and self.customization.platform:
            return self.customization.platform
        else:
            return self._def_platform

    def to_json(self) -> bytes:
        data = asdict(self)
        html = data.pop("html")
        data.pop("id", None)
        return orjson.dumps({"data": data, "html": html, "type": str(self.__class__.__name__)})

    @staticmethod
    def from_json(mega: "MegaD", raw: bytes, id_: int = None) -> "BaseObject":
        data = orjson.loads(raw)
        type_name = data.pop("type")
        html = data.pop("html")
        if type_ := BaseObjectMeta._registry.get(type_name):
            return type_(html=html, mega=mega, id=id_, **data["data"])
        else:
            raise ValueError(f"{type_name=} is not known device type")

    def to(
        self,
        other: Creator[P, T_],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T_:
        co = other(
            self.html,
            self.mega,
            *args,
            **kwargs,
        )
        return co

    async def get_devices(self) -> AsyncIterable["BaseObject"]:
        from .objects import BinaryInput, SensorAdc

        if self.pty == EnumPty.Out:
            async for d in self.to(BaseOut).get_devices():
                yield d
        elif self.pty == EnumPty.I2C:
            async for d in self.to(BaseI2C).get_devices():
                yield d
        elif self.pty == EnumPty.In:
            yield self.to(BinaryInput)
        elif self.pty == EnumPty.DSen:
            async for d in self.to(BaseDsen).get_devices():
                yield d
        elif self.pty == EnumPty.Adc:
            yield self.to(SensorAdc)
        else:
            yield self


@dataclass
class BaseOut(BaseObject):
    mode = ParamDesc("m", EnumOutMode)

    async def get_devices(self) -> AsyncIterable["BaseObject"]:
        from .objects import PWM, Switch, SwitchDs2413

        if self.mode == EnumOutMode.PWM:
            yield self.to(PWM)
        elif self.mode in {EnumOutMode.SW, EnumOutMode.SW_LINK}:
            yield self.to(Switch)
        elif self.mode == EnumOutMode.DS2413:
            data = await self.mega.get(pt=self.port, cmd="list")
            for x in PATT_DS2413_LIST.finditer(data):
                yield self.to(SwitchDs2413, side=0, addr=x.group(1))
                yield self.to(SwitchDs2413, side=1, addr=x.group(1))
            # TODO: добавить обработку множества устройств по cmd=list, вопрос к ablog - какое устройство на
            # главной отображается если их несколько?


@dataclass
class BaseI2C(BaseObject):
    mode = ParamDesc("m", EnumI2CMode)
    category = ParamDesc("gr", EnumI2CGroup)

    async def get_devices(self) -> AsyncIterable["BaseObject"]:
        from .objects import Expander, SensorI2C

        sensor = self.to(BaseSensorI2C)
        # EXPANDER
        if self.category == EnumI2CGroup.Expander:
            exp = self.to(Expander)
            async for d in exp.get_devices():
                yield d
        # SCL
        elif self.mode == EnumI2CMode.SCL:
            return
        else:
            # SENSOR
            if sensor.device:
                for idx, x in enumerate(sensor.device.types):
                    s = self.to(
                        SensorI2C,
                        sensor_info=x,
                        main_idx=idx,
                        is_main=True,
                    )
                    yield s
        # SCAN for more sensors
        scan = BeautifulSoup(await self.mega.get(pt=self.port, cmd="scan"))
        devs: set[str] = set()
        # сначала формируем список i2c_dev
        for a in scan.find_all("a"):
            if isinstance(a, Tag):
                url = a.attrs.get("href", None)
                if url is None:
                    continue
                params = dict(parse_qsl(urlparse(url).query))
                dev = params.get("i2c_dev", None)
                if dev is None:
                    continue
                devs.add(dev)
        for dev in devs:
            if sensor.device and sensor.device == dev:
                # если просканированное устройство совпадает с базовой настройкой порта - пропускаем,
                # т.к. уже добавили выше
                continue
            if dev_enum := EnumI2CSensorDevice.from_str(dev):
                for idx, x in enumerate(dev_enum.types):
                    s = self.to(
                        SensorI2C,
                        sensor_info=x,
                        is_main=False,
                        main_idx=idx,
                    )
                    yield s


@dataclass
class BaseSensorI2C(BaseI2C):
    device = ParamDesc("d", EnumI2CSensorDevice)


@dataclass
class BaseDsen(BaseObject):
    device = ParamDesc("d", EnumDsenDevice)

    async def get_devices(self) -> AsyncIterable["BaseObject"]:
        from .objects import SensorDsen, SensorWB

        if self.device in {EnumDsenDevice.DHT11, EnumDsenDevice.DHT22}:
            s = self.to(SensorDsen)
            s.device_class = SensorDeviceClass.TEMPERATURE
            s.main_idx = 0
            yield s
            s = self.to(SensorDsen)
            s.device_class = SensorDeviceClass.HUMIDITY
            s.main_idx = 0
            yield s
        elif self.device == EnumDsenDevice.ONE_W:
            s = self.to(SensorDsen)
            s.device_class = SensorDeviceClass.TEMPERATURE
            yield s
        elif self.device == EnumDsenDevice.ONE_WBUS:
            data = "Busy"
            while data == "Busy":
                data = await self.mega.get(pt=self.port, cmd="list")
                if data == "Busy":
                    await asyncio.sleep(1)
                for addr, _ in (x.split(":") for x in data.split(":")):
                    w = self.to(SensorWB)
                    w.addr = addr
                    yield w
        # TODO: iB, W26
