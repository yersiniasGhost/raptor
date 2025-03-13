from dataclasses import dataclass
from typing import List, Dict

from .modbus_hardware import ModbusHardware, ModbusClientType


@dataclass
class InviewGateway(ModbusHardware):

    def __post_init__(self):
        self.client_type = ModbusClientType.TCP

    def get_identifier(self, devices: List[dict]) -> Dict[str, str]:
        output = {d["mac"]: "ID is NA" for d in devices}
        return output
