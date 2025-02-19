from typing import Optional, List, Union, Iterable, Dict
from enum import Enum
from dataclasses import dataclass, field
import json


class ModbusDatatype(Enum):
    UINT16 = "uint16"
    INT16 = "int16"
    INT8 = "int8"
    UINT8 = "uint8"
    BOOL = "bool"
    ENUM = "enum"
    FLAG16 = "flag16"   # 16 bit binary flags


class ModbusAcquisitionType(Enum):
    STORE = "store"
    DATA = "data"
    DEBUG = "debug"
    INFO = "info"
    ALARM = "alarm"
    STATUS = "status"


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
    enum_values: Dict[str, str] = field(default_factory=dict)
    length: int = 1
    read_write: str = "RO"

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
                raise ValueError(f"Invalid acquisition type: {self.acquisition_type}")

    def get_addresses(self) -> List[int]:
        """Returns list of all addresses if this is a range register"""
        if self.range_size:
            return list(range(self.address, self.address + self.range_size))
        return [self.address]


    def convert_value(self, value: Union[int, float]) -> float:
        """Apply conversion factor to raw value"""
        return value * self.conversion_factor

    def __hash__(self):
        # Use a combination of fields that uniquely identify the register
        return hash((self.name, self.address))

    def __eq__(self, other):
        if not isinstance(other, ModbusRegister):
            return NotImplemented
        return self.name == other.name and self.address == other.address


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

    def get_registers(self, register_names: Optional[List[str]] = None) -> Iterable[ModbusRegister]:
        for reg in self.registers:
            if not register_names or reg.name in register_names:
                yield reg
