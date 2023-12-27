from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Union

from megad.parsers.units import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CommonUnits,
    SensorDeviceClass,
    UnitOfAirQuality,
    UnitOfLightIntesity,
    UnitOfPressure,
    UnitOfTemperature,
)

Units = Union[
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfAirQuality,
    CommonUnits,
    UnitOfLightIntesity,
    None,
]
map_default_units: dict[str, str] = {
    SensorDeviceClass.TEMPERATURE: UnitOfTemperature.CELSIUS,
    SensorDeviceClass.HUMIDITY: CommonUnits.PERCENTAGE,
    SensorDeviceClass.ILLUMINANCE: UnitOfLightIntesity.LIGHT_LUX,
    SensorDeviceClass.PRESSURE: UnitOfPressure.BAR,
    SensorDeviceClass.ATMOSPHERIC_PRESSURE: UnitOfPressure.BAR,
    SensorDeviceClass.CO2: UnitOfAirQuality.CONCENTRATION_PARTS_PER_MILLION,
    SensorDeviceClass.PM1: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
}


@dataclass
class SensorInfo:
    device_class: SensorDeviceClass | None = None  # None - значит что класс не известен
    unit: Units = None
    name: str | None = None
    i2c_par: int | None = None
    hidden: bool = False
    delay: float = 0

    @property
    def unit_of_measurement(self) -> str | None:
        if self.unit:
            return self.unit
        if self.device_class:
            return map_default_units.get(self.device_class, None)
        return None


def _reg(types_: Iterable[SensorDeviceClass | SensorInfo | None]) -> list[SensorInfo]:
    ret: list[SensorInfo] = []
    for i, x in enumerate(types_):
        if isinstance(x, SensorInfo):
            if x.i2c_par is None:
                x.i2c_par = i
            ret.append(x)
        else:
            ret.append(SensorInfo(device_class=x, i2c_par=i))
    return ret


@dataclass(frozen=True)
class DeviceCategory:
    v: int
    types: Iterable[SensorInfo]
    name: str | None


class reg:
    def __init__(self, v: int, *types: SensorDeviceClass | SensorInfo | None) -> None:
        self.v = v
        self.types = _reg(types)

    def __set_name__(self, owner: "EnumI2CSensorDevice", name: str) -> None:
        self.name = name = name.lower().strip()
        owner._registry[self.v] = self.types
        owner._registry_names[self.v] = self
        owner._registry_str_names[name] = self

    def __get__(self, obj: Any, objtype: Any = None) -> DeviceCategory:
        return DeviceCategory(
            self.v,
            types=self.types,
            name=self.name,
        )


class EnumI2CSensorDevice:
    _registry: dict[int, Iterable[SensorInfo]] = {}
    _registry_names: dict[int, reg] = {}
    _registry_str_names: dict[str, reg] = {}

    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.v == other
        elif isinstance(other, str):
            if i := self._registry_names.get(self.v):
                return i.name.lower() == other.lower()
        return False

    def __hash__(self) -> int:
        return self.v.__hash__()

    @property
    def types(self) -> Iterable[SensorInfo]:
        return self._registry.get(self.v, [])

    NC = 0
    # temp&humidity
    HTU21D = reg(
        1,
        SensorDeviceClass.TEMPERATURE,
        SensorDeviceClass.HUMIDITY,
    )
    SHT31 = reg(
        51,
        SensorDeviceClass.TEMPERATURE,
        SensorDeviceClass.HUMIDITY,
    )
    HTU31D = reg(
        56,
        SensorDeviceClass.TEMPERATURE,
    )
    BMP180 = reg(
        5,
        SensorInfo(SensorDeviceClass.TEMPERATURE, i2c_par=1),
        SensorInfo(SensorDeviceClass.ATMOSPHERIC_PRESSURE, i2c_par=0),
    )
    BMx280 = reg(
        6,
        SensorInfo(SensorDeviceClass.TEMPERATURE, i2c_par=1),
        SensorInfo(SensorDeviceClass.ATMOSPHERIC_PRESSURE, i2c_par=0),
        SensorInfo(SensorDeviceClass.HUMIDITY),
    )
    BME680 = reg(
        53,  # TODO: спросить у Андрея какие i2c_par
        SensorDeviceClass.TEMPERATURE,
        SensorDeviceClass.HUMIDITY,
        SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        SensorDeviceClass.CO2,
    )
    DPS368 = reg(
        55,
        SensorInfo(SensorDeviceClass.TEMPERATURE, i2c_par=1),
        SensorInfo(SensorDeviceClass.ATMOSPHERIC_PRESSURE, i2c_par=0),
    )
    MLX90614 = reg(
        50,
        SensorInfo(SensorDeviceClass.TEMPERATURE, name="temp"),
        SensorInfo(SensorDeviceClass.TEMPERATURE, name="object"),
    )
    MCP9600 = reg(
        52,
        SensorDeviceClass.TEMPERATURE,
        SensorInfo(SensorDeviceClass.TEMPERATURE, i2c_par=1, hidden=True),
    )
    TMP117 = reg(
        54,
        SensorDeviceClass.TEMPERATURE,
    )
    # light
    MAX44009 = reg(
        7,
        SensorDeviceClass.ILLUMINANCE,
    )
    OPT3001 = reg(
        70,
        SensorDeviceClass.ILLUMINANCE,
    )
    BH1750 = reg(
        2,
        SensorDeviceClass.ILLUMINANCE,
    )
    TSL2591 = reg(
        3,
        SensorDeviceClass.ILLUMINANCE,
    )
    # air quality
    T67xx = reg(
        40,
        SensorDeviceClass.CO2,
    )
    SCD4x = reg(
        44,
        SensorDeviceClass.CO2,
        SensorDeviceClass.TEMPERATURE,
        SensorDeviceClass.HUMIDITY,
    )
    HM3301 = reg(
        41,
        SensorDeviceClass.CO2,
    )
    SPS30 = reg(
        42,
        SensorInfo(SensorDeviceClass.PM1, i2c_par=2),
        SensorInfo(SensorDeviceClass.PM25, i2c_par=3),
        SensorInfo(SensorDeviceClass.PM1, i2c_par=4, name="pm4"),
        SensorInfo(SensorDeviceClass.PM10, i2c_par=5),
        SensorInfo(SensorDeviceClass.PM1, i2c_par=6, name="ps"),
        # TODO: доделать остальные
        # ? какие-то манипуляции с вентилятором
    )
    # SSD1306 = 4 TODO: уточнить у андрея
    # LCD1602 = 80
    ADS1115 = reg(
        60,
        SensorDeviceClass.VOLTAGE,
        SensorDeviceClass.VOLTAGE,
        SensorDeviceClass.VOLTAGE,
        SensorDeviceClass.VOLTAGE,
    )
    INA226 = reg(
        61,
        SensorInfo(SensorDeviceClass.CURRENT, i2c_par=1),
        SensorInfo(SensorDeviceClass.VOLTAGE, i2c_par=2),
    )
    Encoder = 30
    PTsensor = reg(
        90,
        SensorInfo(None, i2c_par=1),
        SensorInfo(SensorDeviceClass.PRESSURE, i2c_par=2, delay=1),
        SensorInfo(SensorDeviceClass.TEMPERATURE, i2c_par=3, hidden=True),
    )
    RadSens = reg(
        100,
        None,
    )

    @classmethod
    def from_str(cls, s: str) -> Union["EnumI2CSensorDevice", None]:
        if ret := EnumI2CSensorDevice._registry_str_names.get(s.lower().strip(), None):
            return cls(ret.v)
        return None

    @property
    def name(self) -> str:
        return self._registry_names[self.v].name
