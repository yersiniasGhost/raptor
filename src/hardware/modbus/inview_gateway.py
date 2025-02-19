from dataclasses import dataclass
from .modbus_hardware import ModbusHardware, ModbusClientType


@dataclass
class InviewGateway(ModbusHardware):

    def __post_init__(self):
        self.client_type = ModbusClientType.TCP

