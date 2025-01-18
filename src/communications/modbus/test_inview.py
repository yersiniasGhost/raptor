# Notes:  
#  ip addr add 10.250.250.2/24 dev end0
from pymodbus.client import ModbusSerialClient
from pymodbus.framer import FramerType
import csv
from datetime import datetime
import os
import time
from inview_gateway import InviewGateway

from modbus_map import ModbusMap, ModbusRegister
from modbus_hardware import ModbusHardware

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

        output = [] 
        for register in register_map.get_registers():
            #print(register)
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

                print(f"Unit: {slave_id} addr: {register.address} : {register.description}: {register.data_type}: {value}")
                output.append((register.name, value))

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
    filename = f'inview_slave_{slave_id}.csv'
    file_exists = os.path.exists(filename)

    with open(filename, 'a', newline='') as csvfile:
        fieldnames = ['Timestamp'] + [name for name, _ in data_list]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        # Write header if file is new
        if not file_exists:
            writer.writeheader()

        # Create row with timestamp and values
        row_data = {'Timestamp': timestamp}
        row_data.update({name: value for name, value in data_list})
        writer.writerow(row_data)


if __name__ == "__main__":


    modbus_map = ModbusMap.from_json("inview_alarm.json")
    inview = InviewGateway(host="10.250.250.1", port=502)
    cnt = 0
    while(cnt < 1000000000):
        # Get data from each slave
        r1 = read_holding_registers(inview, modbus_map,slave_id=0)
        #r2 = read_holding_registers(inview, modbus_map,slave_id=1)
        # Write data for each slave to its own CSV file
        print(f"Data logged at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("---------")
        print(r1)
        cnt += 1
        time.sleep(2)
