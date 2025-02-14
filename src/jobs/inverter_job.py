# Notes:
#  ip addr add 10.250.250.2/24 dev end0
import csv
from datetime import datetime
import os
import time

from database.hardware import load_hardware_from_json_file
from database.battery_deployment import BatteryDeployment
from hardware.modbus.modbus import modbus_data_acquisition
from hardware.modbus.modbus_map import ModbusMap
from utils.system_status import collect_system_stats
from utils import LogManager, EnvVars

logger = LogManager().get_logger(__name__)

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

    modbus_map = ModbusMap.from_json("../../data/Sierra25/modbus_map_basic.json")
    inview = load_hardware_from_json_file("../../data/Sierra25/converter_deployment.json")

    batteries = BatteryDeployment.from_json(f"{DATA_PATH}/Esslix/battery_deployment.json")
    register_map = ModbusMap.from_json(f"{DATA_PATH}/Esslix/modbus_map.json")
    cnt = 0
    interval_seconds = EnvVars().data_acquisition_interval

    while True:
        start_time = time.time()
        try:
            # Get data from each slave
            values = modbus_data_acquisition(inview, modbus_map, slave_id=1)
            if values:
                write_to_csv("inverter", 0, values)
            for battery in batteries.each_unit():
                values = modbus_data_acquisition(batteries.hardware, register_map, slave_id=battery.slave_id)
                if values:
                    write_to_csv("battery", battery.slave_id, values)
        except Exception as e:
            logger.error("Failed to perform data acquisition", exc_info=True)
        try:
            sbc_state = collect_system_stats()
            write_to_csv("system", 0, sbc_state)
        except Exception as e:
            logger.error("Failed to perform system status acquisition", exc_info=True)

        logger.info(f"Data logged at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, count: {cnt}")
        elapsed_time = time.time() - start_time
        sleep_time = interval_seconds - elapsed_time

        if sleep_time > 0:
            time.sleep(sleep_time)
        else:
            logger.warning(f"Data acquisition took longer than interval ({elapsed_time:.2f}s > {interval_seconds}s)")
        cnt += 1
