from typing import Dict, Union
import time

from modbus_map import ModbusMap, ModbusDatatype, ModbusRegister
from modbus_hardware import ModbusHardware


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
    else:
        raise ValueError(f"Unsupported data type: {data_type}")

    return value * register.conversion_factor


def modbus_data_acquisition(modbus_hardware: ModbusHardware,
                            modbus_map: ModbusMap, port: str, slave_id: int) -> Dict[ModbusRegister, Union[float, int]]:

    client = modbus_hardware.get_modbus_serial_client(port)
    try:
        if not client.connect():
            print("Failed to connect")
            return {}

        output: Dict[ModbusRegister, Union[float, int]] = {}
        for register in modbus_map.get_data_acquisition_registers():
            # Calculate CRC if necessary...
            # message, crc = modbus_hardware.create_read_message(register, slave_id)

            # Attempt the read.
            address = register.get_addresses()[0]
            result = client.read_holding_registers(address=address, count=1, slave=slave_id)

            if result is None:
                print(f"No response received from port {port}, slave: {slave_id}")
            elif hasattr(result, 'isError') and result.isError():
                print(f"Error reading register: {result}")
            else:
                output[register] = convert_register_value(result.registers[0], register)
                # if register.data_type == ModbusDatatype.UINT16:
                #     output[register] = result.registers[0] * register.conversion_factor
                # elif register.data_type == ModbusDatatype.INT16:
                #     value = result.registers[0]
                #     value = (value - 65536) if value > 32767 else value
                #     output[register] = value * register.conversion_factor
                # elif register.data_type == ModbusDatatype.UINT8:
                #     output[register] = result.registers[0] * register.conversion_factor
                # else:  # what's this?
                #     output[register] = result.registers[0] * register.conversion_factor
            time.sleep(modbus_hardware.MODBUS_SLEEP_BETWEEN_READS)

        return output
    except Exception as e:
        print(f"Error reading modbus: {e}")
    finally:
        client.close()


