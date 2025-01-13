from typing import Optional, List, Union, Iterable
from enum import Enum
from dataclasses import dataclass
import json


class ModbusDatatype(Enum):
    UINT16 = "uint16"
    INT16 = "int16"
    INT8 = "int8"
    UINT8 = "uint8"
    FLAG16 = "flag16"   # 16 bit binary flags


class ModbusAcquisitionType(Enum):
    STORE = "store"
    DEBUG = "debug"
    INFO = "info"


@dataclass
class ModbusRegister:
    name: str
    address: int
    data_type: Union[ModbusDatatype, str]
    range_size: Optional[int] = None  # Number of consecutive registers
    units: str = ""
    conversion_factor: float = 1.0  # e.g., 1/1000 for mV to V
    description: str = ""
    acquisition_type: Union[ModbusAcquisitionType, str] = ModbusAcquisitionType.STORE

    def __post_init__(self):
        # Convert string to enum if string was provided
        if isinstance(self.data_type, str):
            try:
                self.data_type = ModbusDatatype(self.data_type)
            except ValueError:
                raise ValueError(f"Invalid data type: {self.data_type}")
        if isinstance(self.acquisition_type, str):
            try:
                self.acquisition_type = ModbusAcquisitionType(self.acquisition_type)
            except ValueError:
                raise ValueError(f"Invalid data type: {self.acquisition_type}")

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

    def get_data_acquisition_registers(self) -> Iterable[ModbusRegister]:
        for reg in self.registers:
            if reg.data_acquisition:
                yield reg
