# Notes:
#  ip addr add 10.250.250.2/24 dev end0
import csv
from datetime import datetime
import os
import time

from database.hardware import load_hardware_from_json_file
from hardware.modbus.modbus import modbus_data_acquisition_orig
from hardware.modbus.modbus_map import ModbusMap

DATA_PATH = "/root/raptor/data/"


def write_to_csv(filename: str, slave_id: int, data_list: dict):
    """
    Write Modbus data to CSV with timestamp
    data_list: List of tuples [(name, value)]
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    filename = f'{filename}_{slave_id}.csv'
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

    modbus_map = ModbusMap.from_json("../../data/RenogyRover/modbus_map_v1.json")
    rover = load_hardware_from_json_file("../../data/RenogyRover/charge_controller_deployment.json")

    cnt = 0

    while(cnt < 1000000000):
        # Get data from each slave
        values = modbus_data_acquisition_orig(rover, modbus_map, slave_id=1)
        if values:
            write_to_csv("rover", 0, values)

        print(f"Data logged at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("---------")
        cnt += 1
        time.sleep(29)
