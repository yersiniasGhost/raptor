import json
import asyncio
import time
from datetime import datetime
import os
import csv
from typing import Dict, Any, Optional, Union, List
from database.db_utils import get_mqtt_config, get_telemetry_config
from database.database_manager import DatabaseManager
from utils import LogManager, EnvVars
from hardware.hardware_deployment import instantiate_hardware_from_dict, HardwareDeployment
from cloud.mqtt_config import MQTTConfig, FORMAT_FLAT, FORMAT_HIER
from cloud.telemetry_config import TelemetryConfig, MQTT_MODE, REST_MODE
from cloud.mqtt_comms import download_incoming_messages_mqtt, upload_telemetry_data_mqtt, setup_mqtt_listener


class IoTController:

    def __init__(self, store_local: bool):
        # Setup logging with rotation and remote logging if needed
        self.logger = LogManager("iot_controller.log").get_logger(__name__)
        self.running = True
        self._setup_error_handlers()
        self.mqtt_config: MQTTConfig = get_mqtt_config(self.logger)
        self.telemetry_config: TelemetryConfig = get_telemetry_config(self.logger)
        self.telemetry_data: Optional[Dict[str, Any]] = None
        self.store_local = store_local


    def _data_acquisition(self):
        db = DatabaseManager(EnvVars().db_path)
        telemetry_data = {}
        for system in ["BMS", "Converters"]:
            for hardware in db.get_hardware_systems(system):
                self.logger.info(f"ACQ: System: {system} / {hardware['driver_path']} / {hardware['external_ref']}")
                deployment: HardwareDeployment = instantiate_hardware_from_dict(hardware)
                instance_data = deployment.data_acquisition(self.mqtt_config.format)
                telemetry_data = self._format_telemetry(instance_data, deployment, system, telemetry_data)
                self.logger.debug(f"DATA acq:  {instance_data}")
        self.telemetry_data = telemetry_data


    def _format_telemetry(self, inst_data: Dict[str, Union[float, int]],
                          deployment: HardwareDeployment, system: str, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        output_telemetry = telemetry
        if self.mqtt_config.format == FORMAT_FLAT:
            """ Creates flat dictionary like this:  "bms.BMS_12345.current": 10.5 """
            inst_fmt = {f"{system}.{deployment.hardware_id}.{register}": value for register, value in inst_data.items()}
            output_telemetry = output_telemetry | inst_fmt
        elif self.mqtt_config.format == FORMAT_HIER:
            """ Creates hierarchical data format """
            inst_fmt = {deployment.hardware_id: {"measurements": inst_data}}
            output_telemetry[system] = output_telemetry.get(system, {}) | inst_fmt
        return output_telemetry


    async def _handle_incoming_messages(self):
        messages = []
        if self.telemetry_config.mode == MQTT_MODE:
            messages = await download_incoming_messages_mqtt(self.mqtt_config, self.telemetry_config, self.logger)
        elif self.telemetry_config.mode == REST_MODE:
            self.logger.warning("NOT IMPLEMENTED")
            messages = []

        for message in messages:
            self.logger.info(f"Received message: {message}")


    # async def _process_incoming_messages(self):
    #     try:
    #         async for message in self.mqtt_client.messages:
    #             try:
    #                 payload = json.loads(message.payload.decode())
    #                 self.logger.info(f"Received message: {payload}")
    #                 # Process the message - perhaps add to a queue or handle directly
    #                 await self._handle_message(payload)
    #             except json.JSONDecodeError:
    #                 self.logger.error(f"Received invalid JSON on topic {message.topic}")
    #             except Exception as e:
    #                 self.logger.error(f"Error processing message: {e}")
    #     except Exception as e:
    #         self.logger.error(f"Message processing task failed: {e}")
    #         # Reconnect logic could go here

    async def _upload_telemetry_data(self):
        if self.telemetry_config.mode == MQTT_MODE:
            upload_success = await upload_telemetry_data_mqtt(self.mqtt_config, self.telemetry_config, self.logger)
            return upload_success
        elif self.telemetry_config.mode == REST_MODE:
            self.logger.warning("NOT IMPLEMENTED")
            return True
        return False



    def write_to_csv(self, filename: str, slave_id: int, data_list: dict):
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



    async def _store_local_telemetry_data(self):
        pass



    async def main_loop(self):
        """  Main execution loop
             This IoT controller is responsible for executing on a schedule a set of actions:
             a) Data Acquisition:  Read BMS, Converter data, (do we need actuator status?)
             b) Upload to the cloud
             c) Download any instructions from the cloud and act on them
             d) Check new telemetry schedule and update timer.
        """
        interval_seconds = self.telemetry_config.interval
        # self.mqtt_client, self.message_task = setup_mqtt_listener(self.mqtt_config, self.telemetry_config,
        #                                                           self._process_incoming_messages, self.logger)

        while self.running:
            start = time.time()
            try:
                self._data_acquisition()
                # Store data locally first, upload to cloud.  If successful, remove row from database
                if self.telemetry_data:
                    db = DatabaseManager(EnvVars().db_path)
                    db.store_telemetry_data(self.telemetry_data)
                    # Upload to cloud if we have any data
                    upload_success = await self._upload_telemetry_data()
                    if self.store_local:
                        await self._store_local_telemetry_data()
                    if upload_success:
                        db.clear_telemetry_data()
                    else:
                        self.logger.error(f"Wasn't able to upload telemetry data.")
                        # Do something we weren't able to upload the data
                        pass

                # Check for schedule updates / commands / etc. from cloud
                await self._handle_incoming_messages()

                # Wait for next interval
                elapsed = time.time() - start
                sleep_time = max(0, interval_seconds - elapsed)

                # Sleep for the remaining time
                await asyncio.sleep(sleep_time)

            except Exception as e:
                self.logger.critical(f"Critical error in main loop: {str(e)}", exc_info=True)
                # Implement alert mechanism here (email, SMS, etc.)
                elapsed = time.time() - start
                sleep_time = max(0, interval_seconds - elapsed)
                await asyncio.sleep(sleep_time)  # Wait before retrying



    def _setup_error_handlers(self):
        """Setup global error handlers"""

        def handle_exception(loop, context):
            exception = context.get('exception', context['message'])
            self.logger.critical(f"Unhandled error: {str(exception)}", exc_info=True)
            # Implement alert mechanism here
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(handle_exception)


def parse_args():
    parser = argparse.ArgumentParser(description='IoT controller is the long running process that does data'
                                                 ' acquisition, data upload and command processing')
    parser.add_argument('-l', '--local', action="store_true",
                        help="Stores the data in local CSV files for debugging")
    return parser.parse_args()


import argparse

if __name__ == "__main__":
    args = parse_args()
    controller = IoTController(store_local=args.local)
    asyncio.run(controller.main_loop())
