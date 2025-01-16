from pymodbus.client import ModbusSerialClient
from pymodbus.framer import FramerType
import csv
from datetime import datetime
import os
import time

from modbus_map import ModbusMap, ModbusRegister

def read_holding_registers(inview: ModbusHardware, register_map: ModbusMap, slave_id: int =0) -> dict:
    """
    Test BMS communication using specified parameters
    """
    # Create Modbus client with exact specifications from document
    client = inview.get_modbus_client()

    try:
        if not client.connect():
            print("Failed to connect!")
            return {}

        output = {}
        for register in register_map.get_registers():
            print(register)
            address = register.get_addresses()[0]
            # Attempt to read
            result = client.read_holding_registers(
                address=address,
                count=1,
                slave=slave_id
            )

            if result is None:
                print("No response received")
            elif hasattr(result, 'isError') and result.isError():
                print(f"Error reading register: {result}")
            else:
                uint16_value = result.registers[0]
                if register.data_type == "int16":
                    if uint16_value > 32767:
                        value = (uint16_value - 65535) * register.conversion_factor
                    else:
                        value = uint16_value * register.conversion_factor
                else:
                    value = uint16_value * register.conversion_factor

                print(f"Unit: {slave_id} {register.description}: {register.data_type}: {value}")
                output[register.name] = value

            # Wait for frame interval as specified (>100ms)
            time.sleep(0.05)
        return output
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()


def write_to_csv(slave_id, data_list):
    """
    Write Modbus data to CSV with timestamp
    data_list: List of tuples [(name, value)]
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    filename = f'cell_voltage_{slave_id}.csv'
    file_exists = os.path.exists(filename)
    
    with open(filename, 'a', newline='') as csvfile:
        fieldnames = ['Timestamp'] + list(data_list.keys())
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # Write header if file is new
        if not file_exists:
            writer.writeheader()
        
        # Create row with timestamp and values
        row_data = {'Timestamp': timestamp}
        row_data.update({name: value for name, value in data_list.items()})
        writer.writerow(row_data)



if __name__ == "__main__":


    registers = []
    for offset in range(16):
        addr = 0x0031 + offset
        registers.append(
            {
                "name": f"Cell voltage {offset}",
                "data_type": "int16",
                "address": addr,
                "units": "V",
                "conversion_factor": 10.0,
                "description": f"Cell voltage {offset} (V)"
            })


    mb_map = { "registers": registers }

    modbus_map = ModbusMap.from_dict(mb_map)
    cnt = 0
    while(cnt < 1000000000):
        # Get data from each slave
        r1 = read_holding_registers(modbus_map,slave_id=1)
        r2 = read_holding_registers(modbus_map,slave_id=2)
        r3 = read_holding_registers(modbus_map,slave_id=3)
        x 
        # Write data for each slave to its own CSV file
        if r1:  # Only write if we got valid data
            write_to_csv(1, r1)
        if r2:
            write_to_csv(2, r2)
        if r3:
            write_to_csv(3, r3)
            
        print(f"Data logged at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("---------")
        cnt += 1
        time.sleep(120)
