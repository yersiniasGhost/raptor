from typing import Optional, List, Union, Iterable
from dataclasses import dataclass
import json


@dataclass
class ModbusRegister:
    name: str
    address: int
    data_type: str  # "UINT16", "INT16", "UINT8"
    range_size: Optional[int] = None  # Number of consecutive registers
    units: str = ""
    conversion_factor: float = 1.0  # e.g., 1/1000 for mV to V
    description: str = ""
    data_acquisition: bool = False


    def get_addresses(self) -> List[int]:
        """Returns list of all addresses if this is a range register"""
        if self.range_size:
            return list(range(self.address, self.address + self.range_size))
        return [self.address]


    def convert_value(self, value: Union[int, float]) -> float:
        """Apply conversion factor to raw value"""
        return value * self.conversion_factor


@dataclass
class ModbusMap:
    registers: List[ModbusRegister]


    @classmethod
    def from_json(cls, json_file: str) -> 'ModbusMap':
        with open(json_file, 'r') as f:
            data = json.load(f)
            return cls.from_dict(data)

    @classmethod
    def from_dict(cls, register_map: dict) -> 'ModbusMap':
        registers = [ModbusRegister(**reg) for reg in register_map['registers']]
        return cls(registers=registers)

    # better to use a Dict?
    def get_register_by_name(self, name: str) -> Optional[ModbusRegister]:
        """Find register by name"""
        for reg in self.registers:
            if reg.name == name:
                return reg
        return None

    def get_registers(self) -> Iterable[ModbusRegister]:
        for reg in self.registers:
            yield reg
