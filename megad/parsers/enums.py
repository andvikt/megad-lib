from enum import Enum


class EnumServerType(int, Enum):
    HTTP = 0
    MQTT = 1


class EnumUartType(int, Enum):
    Disabled = 0
    GSM = 1
    RS485 = 2


class EnumPty(int, Enum):
    NC = 255
    In = 0
    Out = 1
    Adc = 2
    DSen = 3
    I2C = 4


class EnumOutMode(int, Enum):
    SW = 0
    PWM = 1
    SW_LINK = 3
    DS2413 = 2
    WS281X = 4


class EnumI2CMode(int, Enum):
    NC = 0
    SDA = 1
    SCL = 2


class EnumI2CGroup(int, Enum):
    ANY = 0
    Temp_Hum = 1
    Light = 2
    Expander = 3
    Air_Quality = 5
    Misc = 4


class EnumInMode(int, Enum):
    P = 0
    P_R = 1
    R = 2
    C = 3


class EnumI2CExpanderDevice(int, Enum):
    NC = 0
    MCP230XX = 20
    PCA9685 = 21


class EnumDsenDevice(int, Enum):
    DHT11 = 1
    DHT22 = 2
    ONE_W = 3
    ONE_WBUS = 5
    iB = 4
    W26 = 6

    @property
    def id_suffix(self) -> list[str] | None:
        if s := _map_suffix.get(self):
            return s
        return None


_map_suffix: dict[int, list[str]] = {
    EnumDsenDevice.DHT11: ["temp", "hum"],
    EnumDsenDevice.DHT22: ["temp", "hum"],
}


class EnumOneWireMode(int, Enum):
    Norm = 0
    GREATER = 1
    LOWER = 2
    LOWER_GREATER = 3
