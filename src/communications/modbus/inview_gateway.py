from dataclasses import dataclass
from typing import Tuple, Optional, Dict
from modbus_hardware import ModbusHardware, ModbusClientType
from modbus_map import ModbusRegister, ModbusDatatype


@dataclass
class InviewGateway(ModbusHardware):

    def __post_init__(self):
        self.client_type = ModbusClientType.TCP

