from typing import Dict, Union
import csv
from datetime import datetime
import os
import time
from modbus_map import ModbusMap, ModbusRegister
from modbus import modbus_data_acquisition
from eve_battery import EveBattery


def write_to_csv(slave_id, data_list: dict):
    """
    Write Modbus data to CSV with timestamp
    data_list: List of tuples [(name, value)]
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    filename = f'abs_modbus_slave_{slave_id}.csv'
    file_exists = os.path.exists(filename)
    
    with open(filename, 'a', newline='') as csvfile:
        fieldnames = ['Timestamp'] + list(data_list.keys())
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # Write header if file is new
        if not file_exists:
            writer.writeheader()
        
        # Create row with timestamp and values
        row_data: dict = {'Timestamp': timestamp}
        row_data.update(data_list)
        writer.writerow(row_data)


if __name__ == "__main__":

    mb_map = {
        "registers": [
            {
                "name": "Current (10mA)",
                "data_type": "int16",
                "address": 0x0000,
                "units": "A",
                "conversion_factor": 0.01,
                "description": "Battery current in A"
            },
            {
                "name": "SOC (%)",
                "data_type": "uint8",
                "address": 0x0002,
                "units": "%",
                "conversion_factor": 0.01,
                "description": "SOC (%)"
            },
            {
                "name": "Remain capacity (10mAH)",
                "data_type": "uint16",
                "address": 0x0004,
                "units": "AH",
                "conversion_factor": 0.01,
                "description": "The remaining capacity of the battery in AH"
            }

        ]
    }

    modbus_map = ModbusMap.from_dict(mb_map)
    eve_battery = EveBattery()
    port: str = '/dev/ttyS11'

    cnt = 0
    while cnt < 1000000000:
        start = time.time_ns()
        # Get data from each slave
        r = []
        for i in range(3):
            s = i + 1
            read_values = modbus_data_acquisition(eve_battery, modbus_map, port, slave_id=s)
            print(f"Slave: {s}, {read_values}")
            if read_values:
                write_to_csv(s, read_values)

        print(f"Data logged at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("---------")
        cnt += 1
        sleep = 30 - (time.time_ns() - start) / 1e9
        time.sleep(sleep)
