# Notes:
#  ip addr add 10.250.250.2/24 dev end0
import csv
from datetime import datetime
import os
import time
from database.inverters import load_inverter_from_json_file
from communications.modbus.modbus import modbus_data_acquisition
from communications.modbus.modbus_map import ModbusMap


def write_to_csv(slave_id, data_list):
    """
    Write Modbus data to CSV with timestamp
    data_list: List of tuples [(name, value)]
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    filename = f'inview2_slave_{slave_id}.csv'
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

    modbus_map = ModbusMap.from_json("../../../data/Sierra25/modbus_map_basic.json")
    inview = load_inverter_from_json_file("../../../data/Sierra25/converter_deployment.json")
    cnt = 0

    while(cnt < 1000000000):
        # Get data from each slave
        values = modbus_data_acquisition(inview, modbus_map, slave_id=1)
        write_to_csv(0, values)
        print(f"Data logged at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("---------")
        cnt += 1
        time.sleep(29)
