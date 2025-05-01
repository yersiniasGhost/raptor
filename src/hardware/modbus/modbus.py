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


def modbus_data_acquisition_orig(modbus_hardware: ModbusHardware,
                                 modbus_map: ModbusMap, slave_id: int,
                                 logger) -> Dict[str, Union[float, int]]:
    client = modbus_hardware.get_modbus_client()
    try:
        if not client.connect():
            logger.error("Failed to connect")
            return {}

        output: Dict[str, Union[float, int]] = {}
        for register in modbus_map.register_iterator():
            # Calculate CRC if necessary...
            # message, crc = modbus_hardware.create_read_message(register, slave_id)

            # Attempt the read.
            address = int(register.get_addresses()[0])
            result = client.read_holding_registers(address=address, count=1, slave=slave_id)
            if result is None:
                logger.info(f"No response received from port {modbus_hardware.port}, slave: {slave_id}")
            elif hasattr(result, 'isError') and result.isError():
                logger.info(f"Error reading register: {result}")
            else:
                output[register.name] = convert_register_value(result.registers[0], register)

        return output
    except Exception as e:
        logger.exception(f"Error reading modbus: {e}")
    finally:
        client.close()


def modbus_data_write(modbus_hardware: ModbusHardware,
                      modbus_map: ModbusMap,
                      slave_id: int,
                      register_name: str,
                      value: Union[float, int],
                      logger=None) -> bool:
    if not logger:
        logger = LogManager().get_logger("ModbusHardware")

    client = modbus_hardware.get_modbus_client()
    try:
        if not client.connect():
            logger.warning("Failed to connect to Modbus client.")
            return False

        # Find the register by name
        register = modbus_map.get_register_by_name(register_name)
        if not register:
            logger.warning(f"Register {register_name} not found in map")
            return False

        if register.read_write != "RW":
            logger.warning(f"Cannot write, register is not RW: {register}")
            return False
        # Convert the value to the appropriate format for the register
        try:
            converted_value = prepare_value_for_register(value, register)
        except ValueError as e:
            logger.exception(f"Error converting value: {e}")
            return False

        # Attempt write to register
        address = register.get_addresses()[0]
        result = client.write_register(address=address, value=converted_value, slave=slave_id)

        if result is None:
            logger.error(f"No response received from port {modbus_hardware.port}, slave: {slave_id}")
            return False
        elif hasattr(result, 'isError') and result.isError():
            logger.error(f"Error writing to register: {result}")
            return False
        return True

    except Exception as e:
        logger.error(f"Error writing to modbus: {e}")
        return False
    finally:
        client.close()


def prepare_value_for_register(value: Union[float, int], register: ModbusRegister) -> int:
    """Convert a value to the appropriate format for writing to a register."""
    data_type = register.data_type
    if data_type == ModbusDatatype.INT16:
        # Ensure value is within INT16 range
        if not -32768 <= value <= 32767:
            raise ValueError(f"Value {value} out of range for INT16")
        return int(value)

    elif data_type == ModbusDatatype.UINT16:
        # Ensure value is within UINT16 range
        if not 0 <= value <= 65535:
            raise ValueError(f"Value {value} out of range for UINT16")
        return int(value)

    elif data_type == ModbusDatatype.INT8:
        # Ensure value is within INT8 range
        if not -128 <= value <= 127:
            raise ValueError(f"Value {value} out of range for INT8")
        return int(value)

    else:
        raise ValueError(f"Unsupported register type: {register.type}")
