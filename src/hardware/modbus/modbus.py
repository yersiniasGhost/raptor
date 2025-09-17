from typing import Dict, Union, List

from .modbus_map import ModbusMap, ModbusDatatype, ModbusRegister
from .modbus_hardware import ModbusHardware
from utils import LogManager



def convert_register_value(raw_value: int, register: ModbusRegister) -> float:
    """Convert raw register value based on data type and apply conversion factor"""
    data_type = register.data_type
    if data_type == ModbusDatatype.UINT16:
        # UINT16: 0 to 65535, no conversion needed
        value = raw_value & 0xFFFF  # Ensure 16-bit unsigned

    elif data_type == ModbusDatatype.INT16:
        # INT16: -32768 to 32767
        raw_value = raw_value & 0xFFFF  # Ensure 16-bit
        # Convert to signed using 2's complement
        value = (raw_value - 65536) if (raw_value & 0x8000) else raw_value
    elif data_type == ModbusDatatype.UINT8:
        # UINT8: 0 to 255
        # Assuming it's in the low byte
        value = raw_value & 0xFF  # Mask to get only lower 8 bits
    elif data_type == ModbusDatatype.FLAG16:
        value = 0
    else:
        raise ValueError(f"Unsupported data type: {data_type}")

    return value * register.conversion_factor



