import argparse
import asyncio
import time
from datetime import datetime
import os
import csv
from typing import Dict, Union, Optional, Any
from database.db_utils import get_mqtt_config, get_telemetry_config, get_raptor_configuration
from database.database_manager import DatabaseManager
from utils import LogManager, EnvVars
from hardware.hardware_deployment import instantiate_hardware_from_dict, HardwareDeployment
from config.mqtt_config import MQTTConfig, FORMAT_FLAT, FORMAT_HIER, FORMAT_LINE_PROTOCOL
from config.telemetry_config import TelemetryConfig, MQTT_MODE, REST_MODE
from cloud.mqtt_comms import upload_telemetry_data_mqtt
from utils.system_status import collect_system_stats


class IoTController:

    def __init__(self, store_local: bool):
        # Setup logging with rotation and remote logging if needed
        self.logger = LogManager("iot_controller.log").get_logger("IoTController")
        self.running = True
        self.mqtt_config: MQTTConfig = get_mqtt_config(self.logger)
        self.telemetry_config: TelemetryConfig = get_telemetry_config(self.logger)
        self.telemetry_data: Optional[Dict[str, Any]] = None
        self.raptor_configuration = get_raptor_configuration(self.logger)
        self.store_local = True
        self.mqtt_task = None
        self.system_measurements = {}


    async def _data_acquisition(self) -> dict:
        """
        Read the data only.   Holds data in a dictionary (internal format)
        """

        db = DatabaseManager(EnvVars().db_path)
        telemetry_data = {}
        sz = 0
        system_measurements = {}
        for system in ["BMS", "Converters"]:
            hardware_measurements = {}
            for hardware in db.get_hardware_systems(system):
                deployment: HardwareDeployment = instantiate_hardware_from_dict(hardware)

                self.logger.info(f"ACQ: System: {system} / {hardware['driver_path']} / {hardware['external_ref']}")
                instance_data = deployment.data_acquisition()
                sz += len(instance_data)
                if self.store_local:
                    self._store_local_telemetry_data(system, instance_data)
                hardware_measurements[deployment.hardware_id] = instance_data
                self.logger.debug(f"DATA acq:  {instance_data}")
            system_measurements[system] = hardware_measurements
        self.system_measurements = system_measurements
        self.logger.info(f"Data acq: collected from {sz} devices.")
        return system_measurements


    async def _data_acquisition_telemetry(self):
        """ Read the data and format for telemetry (as opposed to averaging) """
        system_measurements = await self._data_acquisition()
        self.telemetry_data = self._format_telemetry_data(system_measurements)

        # Store data locally first, upload to cloud.  If successful, remove row from database
        data = self.telemetry_data.get("data", [])
        if data:
            db = DatabaseManager(EnvVars().db_path)
            db.store_telemetry_data(self.telemetry_data)
            # Upload to cloud if we have any data
            upload_success = await self._upload_telemetry_data()

            if upload_success:
                db.clear_telemetry_data()
            else:
                self.logger.error(f"Wasn't able to upload telemetry data.")
                # Do something we weren't able to upload the data
                pass

        try:
            sbc_state = {0: collect_system_stats()}
            self._store_local_telemetry_data("RAPTOR", sbc_state)
        except Exception as e:
            self.logger.error("Failed to perform system status acquisition", exc_info=True)



    def _format_telemetry_data(self, system_measurements: Dict[str, Any]) -> Dict[str, Any]:
        """ Example system measurements data:
        { "BMS": { "hardwareID":  { device_id: {'DC Voltage': 53.5, 'DC Current': 0.30000000000000004, 'DC Power': 10, 'Phase1Current': 0.0, 'Phase1Voltage': 121.7, 'Phase1TruePower': 0, 'Phase1ApparentPower': 0},
                        1: {'Current': 1.62, 'Pack Voltage': 53.11, 'State of Charge': 37, 'Remaining Capacity': 36.97}, 2: {'Current': 1.54, 'Pack Voltage': 53.1, 'State of Charge': 36, 'Remaining Capacity': 36.27},
                        3: {'Current': 1.57, 'Pack Voltage': 53.1, 'State of Charge': 40, 'Remaining Capacity': 40.31}} }
        """
        timestamp = int(time.time() * 1000000000)
        if True or self.mqtt_config.format == FORMAT_LINE_PROTOCOL:
            lines = []
            for system, system_data in system_measurements.items():
                measurement = f"{system}"
                for hardware, hardware_data in system_data.items():
                    for device_id, m_data in hardware_data.items():
                        if m_data:
                            tags = [f"raptor={self.raptor_configuration.raptor_id}", f"hardware_id={hardware}",
                                    f"device_id={device_id}"]
                            fields = [f"{point}={value}" for point, value in m_data.items()]
                            tag_str = ','.join(tags)
                            field_str = ','.join(fields)
                            line = f"{measurement},{tag_str} {field_str} {timestamp}"
                            lines.append(line)
            self.logger.info(f"Line protocol:  {len(lines)} lines collected.")
            return {"mode": FORMAT_LINE_PROTOCOL, "data": lines}
        else:
            return {}



    def _format_telemetry(self, inst_data: Dict[str, Union[float, int]],
                          deployment: HardwareDeployment, system: str, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        output_telemetry = telemetry
        if self.mqtt_config.format == FORMAT_FLAT:
            """ Creates flat dictionary like this:  "bms.BMS_12345.current": 10.5 """
            for device_id, m_data in inst_data.items():
                for point, value in m_data.items():
                    inst_fmt = {f"{system}.{deployment.hardware_id}.{device_id}.{point}": value}
                    output_telemetry = output_telemetry | inst_fmt
        elif self.mqtt_config.format == FORMAT_LINE_PROTOCOL:

            measurement = f"{system}"
            tags = [f"raptor={self.raptor_configuration.raptor_id}"]
            fields = []
            for device_id, m_data in inst_data.items():
                tags.append(f"device_id={device_id}")
                fields = [f"{point}={value}" for point, value in m_data.items()]
            tag_str = ','.join(tags)
            field_str = ','.join(fields)
            timestamp = int(time.time() * 1000000000)
            line = f"{measurement},{tag_str} {field_str} {timestamp}"

        elif self.mqtt_config.format == FORMAT_HIER:
            """ Creates hierarchical data format """
            inst_fmt = {deployment.hardware_id: {"measurements": inst_data}}
            output_telemetry[system] = output_telemetry.get(system, {}) | inst_fmt
        return output_telemetry


    async def _upload_telemetry_data(self):
        if self.telemetry_config.mode == MQTT_MODE:
            upload_status = await upload_telemetry_data_mqtt(self.mqtt_config, self.telemetry_config, self.logger)
            self.logger.info(f"MQTT upload status: {upload_status}")
            return upload_status
        elif self.telemetry_config.mode == REST_MODE:
            self.logger.warning("NOT IMPLEMENTED")
            return True
        return False


    def _store_local_telemetry_data(self, system: str, data: dict):
        """
        Write Modbus data to CSV with timestamp
        data_list: List of tuples [(name, value)]
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for slave_id, data_list in data.items():
            if not len(data_list):
                continue
            if system == "BMS":
                filename = f'battery2_{slave_id}.csv'
            elif system == "Converters":
                filename = f"inverter2_{slave_id}.csv"
            elif system == "RAPTOR":
                filename = f"system_0.csv"
            else:
                self.logger.warning(f"No such system for writing local data: {system}")
                return
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


    async def shutdown(self):
        print("SHUTDOWN")
        self.running = False
        DatabaseManager().close()


    async def main_loop(self):
        """  Main execution loop
             This IoT controller is responsible for executing on a schedule a set of actions:
             a) Data Acquisition:  Read BMS, Converter data, (do we need actuator status?)
             b) Upload to the cloud
             c) Download any instructions from the cloud and act on them
             d) Check new telemetry schedule and update timer.
        """
        self.logger.info(f"Starting up IoT Controller application.")
        interval_seconds = self.telemetry_config.interval

        while self.running:
            start = time.time()
            try:
                await self._data_acquisition_telemetry()

                # Wait for next interval
                elapsed = time.time() - start
                sleep_time = max(0, interval_seconds - elapsed)

                # Sleep for the remaining time
                await asyncio.sleep(sleep_time)

            except Exception as e:
                self.logger.critical(f"Critical error in main loop: {str(e)}", exc_info=True)
                # Implement alert mechanism here (email, SMS, etc.)
                elapsed = time.time() - start
                sleep_time = max(min(interval_seconds, 30), interval_seconds - elapsed)  # Cap error retry to 30 seconds
                await asyncio.sleep(sleep_time)  # Wait before retrying


def parse_args():
    parser = argparse.ArgumentParser(description='IoT controller is the long running process that does data'
                                                 ' acquisition, data upload and command processing')
    parser.add_argument('-l', '--local', action="store_true",
                        help="Stores the data in local CSV files for debugging")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    controller = IoTController(store_local=args.local)
    asyncio.run(controller.main_loop())


# Example messages's:
# mosquitto_pub -h localhost -t "raptors/67b672097fc4a4b18476b1ed/messages" -m '{"action":"firmware_update", "params": {"tag":"2025-03-03-lf-influxdb"}}'
