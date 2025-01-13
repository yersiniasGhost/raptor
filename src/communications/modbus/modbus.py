import time

from modbus_map import ModbusMap, ModbusDatatype
from modbus_hardware import ModbusHardware


def modbus_data_acquisition(modbus_hardware: ModbusHardware, modbus_map: ModbusMap, port: str, slave_id: int):

    client = modbus_hardware.get_modbus_serial_client(port)
    try:
        if not client.connect():
            print("Failed to connect")
            return

        output = {}
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
                if register.data_type == ModbusDatatype.UINT16:
                    output[register.name] = result.registers[0] * register.conversion_factor
                elif register.data_type == ModbusDatatype.INT16:
                    value = result.registers[0]
                    value = (value - 65536) if value > 32767 else value
                    output[register.name] = value * register.conversion_factor
                else:  # what's this?
                    output[register.name] = result.registers[0] * register.conversion_factor

            time.sleep(modbus_hardware.MODBUS_SLEEP_BETWEEN_READS)

        return output
    except Exception as e:
        print(f"Error reading modbus: {e}")
    finally:
        client.close()


