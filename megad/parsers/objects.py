from collections.abc import AsyncIterable
from dataclasses import dataclass

from .base import BaseDsen, BaseI2C, BaseObject, BaseOut, BaseSensorI2C
from .cache import cached_property
from .const import PATT_EXT230
from .enums import EnumI2CExpanderDevice, EnumInMode, EnumOneWireMode
from .i2c_sensors import SensorInfo
from .param_desc import ParamDesc
from .tools import safe_float, safe_int


@dataclass
class SensorOneWire(BaseDsen):
    mode = ParamDesc("m", EnumOneWireMode)
    val = ParamDesc("misc", safe_float)
    histersis = ParamDesc("hst", safe_float)

    _def_platform = "sensor"


@dataclass
class SensorI2C(BaseSensorI2C):
    sensor_info: SensorInfo | None = None
    is_main: bool = True  # представлен ли сенсор на основной странице порта
    main_idx: int | None = None  # порядковый номер датчика на основной странице порта

    _def_platform = "sensor"

    @cached_property
    def id_suffix(self) -> str | None:
        names = [self.device.name] if self.device else []
        if self.sensor_info and self.sensor_info.name:
            names.append(self.sensor_info.name)
        return "_".join(names) if names else None


@dataclass
class SensorAdc(BaseObject):
    mode = ParamDesc("m", EnumOneWireMode)
    val = ParamDesc("misc", safe_float)
    histersis = ParamDesc("hst", safe_float)

    _def_platform = "sensor"


@dataclass
class Expander(BaseI2C):
    device = ParamDesc("d", EnumI2CExpanderDevice)

    async def get_devices(self) -> AsyncIterable["BaseObject"]:
        if self.device == EnumI2CExpanderDevice.NC:
            return
        if self.device == EnumI2CExpanderDevice.MCP230XX:
            data = await self.mega.get(pt=self.port, cf=1)
            for port in PATT_EXT230.finditer(data):
                ext = port.group(1)
                tp = port.group(2)
                if tp == "OUT":
                    yield self.to(SwitchExpander, ext=int(ext))
                elif tp == "IN":
                    yield self.to(BinaryInputExpander, ext=int(ext))
        elif self.device == EnumI2CExpanderDevice.PCA9685:
            for i in range(16):
                yield self.to(PwmExpander, ext=i)


@dataclass
class Switch(BaseOut):
    group = ParamDesc("grp", safe_int)

    _def_platform = "light"


@dataclass
class SwitchDs2413(BaseOut):
    addr: str = ""
    side: int = 0

    _def_platform = "light"

    @cached_property
    def id_suffix(self) -> str | None:
        return f"{self.addr}_{'a' if self.side == 1 else 'b'}"


@dataclass
class SwitchExpander(Expander):
    ext: int = -1

    _def_platform = "light"


@dataclass
class BinaryInputExpander(Expander):
    ext: int = -1

    _def_platform = "binary_sensor"


@dataclass
class PWM(Switch):
    min_ = ParamDesc("pwmm", safe_int)
    smooth = ParamDesc("misc", bool)

    _def_platform = "light"


@dataclass
class PwmExpander(Expander):
    ext: int = -1

    _def_platform = "light"


@dataclass
class BinaryInput(BaseObject):
    _def_platform = "binary_sensor"
    act = ParamDesc("ecmd", str)
    net = ParamDesc("eth", str)
    mode = ParamDesc("m", EnumInMode)


@dataclass
class SensorDsen(BaseDsen):
    main_idx: int = 0
    device_class: str | None = None
    unit_of_measurement: str | None = None

    _def_platform = "sensor"

    @cached_property
    def id_suffix(self) -> str | None:
        if self.device and self.device.id_suffix:
            return self.device.id_suffix[self.main_idx]
        return None


@dataclass
class SensorWB(BaseDsen):
    addr: str | None = None

    _def_platform = "sensor"

    @cached_property
    def id_suffix(self) -> str | None:
        return self.addr
