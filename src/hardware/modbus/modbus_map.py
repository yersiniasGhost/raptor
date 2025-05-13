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
    ASCII16 = "ascii16"  # two byes of ASCII characters
    ASCII8 = "ascii8"


class ModbusAcquisitionType(Enum):
    STORE = "store"
    DATA = "data"
    DEBUG = "debug"
    INFO = "info"
    ALARM = "alarm"
    STATUS = "status"


class ModbusRegisterType(Enum):
    HOLDING = 'holding'
    INPUT = 'input'
    CONTROL = 'control'


@dataclass
class ModbusRegister:
    name: str
    address: int
    data_type: Union[ModbusDatatype, str]
    range_size: int = 1  # Number of consecutive registers
    units: str = ""
    conversion_factor: float = 1.0  # e.g., 1/1000 for mV to V
    description: str = ""
    acquisition_type: Union[ModbusAcquisitionType, str] = ModbusAcquisitionType.STORE
    enum_values: Dict[str, str] = field(default_factory=dict)
    length: int = 1
    access: str = "RO"
    slave_id: Optional[int] = None
    type: Union[ModbusRegisterType, str] = ModbusRegisterType.HOLDING

    def __post_init__(self):
        # Ensure the name has no spaces:
        self.name = self.name.replace(' ', '_')
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
    registers: Dict[str, ModbusRegister]


    @classmethod
    def from_json(cls, json_file: str) -> 'ModbusMap':
        with open(json_file, 'r') as f:
            data = json.load(f)
            return cls.from_dict(data)

    @classmethod
    def from_dict(cls, register_map: dict) -> 'ModbusMap':
        registers = {name: ModbusRegister(**reg) for name, reg in register_map.items()}
        return cls(registers=registers)

    # better to use a Dict?
    def get_register_by_name(self, name: str) -> Optional[ModbusRegister]:
        return self.registers.get(name, None)


    def get_registers(self, names: List[str]) -> List[ModbusRegister]:
        regs = []
        for name in names:
            reg = self.registers.get(name, None)
            if reg:
                regs.append(reg)
        return regs

    def register_iterator(self, register_names: Optional[List[str]] = None) -> Iterable[ModbusRegister]:
        if not register_names:
            for name, register in self.registers:
                yield register
        else:
            for name in register_names:
                reg = self.registers.get(name, None)
                if reg:
                    yield reg
