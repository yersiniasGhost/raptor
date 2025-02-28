import argparse
import asyncio
import time
from datetime import datetime
import os
import csv
from typing import Dict, Union, Optional, Any
from database.db_utils import get_mqtt_config, get_telemetry_config
from database.database_manager import DatabaseManager
from utils import LogManager, EnvVars
from hardware.hardware_deployment import instantiate_hardware_from_dict, HardwareDeployment
from cloud.mqtt_config import MQTTConfig, FORMAT_FLAT, FORMAT_HIER
from cloud.telemetry_config import TelemetryConfig, MQTT_MODE, REST_MODE
from cloud.mqtt_comms import upload_telemetry_data_mqtt, setup_mqtt_listener, upload_command_response
from actions.action_factory import ActionFactory
from actions.action_status import ActionStatus
from utils import get_mac_address


class IoTController:

    def __init__(self, store_local: bool):
        # Setup logging with rotation and remote logging if needed
        self.logger = LogManager("iot_controller.log").get_logger("IoTController")
        self.running = True
        self._setup_error_handlers()
        self.mqtt_config: MQTTConfig = get_mqtt_config(self.logger)
        self.telemetry_config: TelemetryConfig = get_telemetry_config(self.logger)
        self.telemetry_data: Optional[Dict[str, Any]] = None
        self.store_local = True
        self.mqtt_task = None
        self.unformatted_data = {}


    def _data_acquisition(self):
        db = DatabaseManager(EnvVars().db_path)
        telemetry_data = {}
        sz = 0
        self.unformatted_data = {}
        for system in ["BMS", "Converters"]:
            for hardware in db.get_hardware_systems(system):
                self.logger.info(f"ACQ: System: {system} / {hardware['driver_path']} / {hardware['external_ref']}")
                deployment: HardwareDeployment = instantiate_hardware_from_dict(hardware)
                instance_data = deployment.data_acquisition()
                if self.store_local:
                    self._store_local_telemetry_data(system, instance_data)
                self.unformatted_data = self.unformatted_data | instance_data
                sz += len(instance_data)
                telemetry_data = self._format_telemetry(instance_data, deployment, system, telemetry_data)
                self.logger.debug(f"DATA acq:  {instance_data}")
        self.telemetry_data = telemetry_data
        self.logger.info(f"Data acq: collected {sz} data points.")


    def _format_telemetry(self, inst_data: Dict[str, Union[float, int]],
                          deployment: HardwareDeployment, system: str, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        output_telemetry = telemetry
        if self.mqtt_config.format == FORMAT_FLAT:
            """ Creates flat dictionary like this:  "bms.BMS_12345.current": 10.5 """
            for device_id, measurement in inst_data.items():
                for point, value in measurement.items():
                    inst_fmt = {f"{system}.{deployment.hardware_id}.{device_id}.{point}": value}
                    output_telemetry = output_telemetry | inst_fmt
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
            else:
                filename = f"inverter2_{slave_id}.csv"
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

    async def _respond_to_message(self, status: ActionStatus, action_id: str, payload: Optional[dict] = None):
        payload = payload | {"mac": get_mac_address(), "action_id": action_id, "action_status": status}
        self.logger.info(f"Responding to received message with status:{status}, id: {action_id}, {payload}")

        await upload_command_response(self.mqtt_config, self.telemetry_config,
                                      status.value, payload, self.logger)


    async def _handle_mqtt_messages(self):
        """Task to handle MQTT messages"""
        self.logger.info("Initiating incoming message handler.")
        retry_count = 0
        max_retries = 3
        retry_delay = 3
        while self.running:
            try:
                async for payload in setup_mqtt_listener(self.mqtt_config, self.telemetry_config, self.logger):
                    retry_count = 0
                    self.logger.info(f"Received message: {payload}")
                    action_name = payload.get('action')
                    params = payload.get('params', {})
                    action_id = payload.get('action_id', "NA")
                    try:
                        if action_name:
                            status, cmd_response = await ActionFactory.execute_action(action_name, params,
                                                                                      self.telemetry_config,
                                                                                      self.mqtt_config)
                            if status == ActionStatus.NOT_IMPLEMENTED:
                                cmd_response = {"message": f"Action not implemented: {action_name}"}
                                await self._respond_to_message(status, action_id, cmd_response)

                            else:
                                await self._respond_to_message(status, action_id, cmd_response)

                        else:
                            self.logger.error(f"Received message with no action specified")
                            await self._respond_to_message(ActionStatus.INVALID_PARAMS, action_id,
                                                           payload={"message": f"Invalid action: {payload}"})
                    except Exception as e:
                        self.logger.error(f"Error processing MQTT message: {e}", exc_info=True)
                        # Try to notify about the error
                        try:
                            await self._respond_to_message(ActionStatus.ERROR, action_id,
                                                           payload={"message": f"Error processing action: {str(e)}"})
                        except Exception:
                            pass
                        # Continue processing next message
                        continue

            except asyncio.CancelledError:
                self.logger.info("MQTT handling task was cancelled, exiting")
                break
            except Exception as e:
                self.logger.error(f"MQTT connection failed with error: {e}", exc_info=True)

                # Implement exponential backoff
                retry_count += 1
                if retry_count > max_retries:
                    retry_delay = min(60, retry_delay * 2)  # Max delay of 60 seconds

                self.logger.warning(f"Reconnecting to MQTT in {retry_delay} seconds (attempt {retry_count})")
                await asyncio.sleep(retry_delay)


    def _on_handle_mqtt_messages_exit(self, task):
        try:
            # This will raise the exception if the task failed
            result = task.result()
            self.logger.info("MQTT handling task completed normally")
        except asyncio.CancelledError:
            self.logger.info("MQTT handling task was cancelled")
        except Exception as e:
            self.logger.error(f"MQTT handling task failed with exception: {e}")
            # Restart the task if needed
            self.mqtt_task = asyncio.create_task(self._handle_mqtt_messages())
            self.logger.warning("MQTT tasks restarted.")

    async def shutdown(self):
        print("SHUTDOWN")
        self.running = False
        DatabaseManager().close()
        if self.mqtt_task:
            self.mqtt_task.cancel()


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
        self._start_mqtt_task()
        await asyncio.create_task(self._monitor_tasks())

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

                    if upload_success:
                        db.clear_telemetry_data()
                    else:
                        self.logger.error(f"Wasn't able to upload telemetry data.")
                        # Do something we weren't able to upload the data
                        pass

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



    def _start_mqtt_task(self):
        """Start MQTT handling task with error recovery"""
        if self.mqtt_task and not self.mqtt_task.done():
            # Cancel existing task if running
            self.mqtt_task.cancel()

        self.mqtt_task = asyncio.create_task(self._handle_mqtt_messages())
        self.mqtt_task.add_done_callback(self._on_handle_mqtt_messages_exit)
        self.logger.info("MQTT task started")



    async def _monitor_tasks(self):
        """Monitor critical tasks and restart them if they fail"""
        while self.running:
            # Check MQTT task
            if self.mqtt_task and self.mqtt_task.done():
                try:
                    # This will raise any exception that occurred
                    self.mqtt_task.result()
                    self.logger.warning("MQTT task completed unexpectedly")
                except asyncio.CancelledError:
                    # Task was cancelled intentionally, no need to restart
                    pass
                except Exception as e:
                    self.logger.error(f"MQTT task failed with error: {e}")

                # Restart MQTT task if it's not running and should be
                if self.running:
                    self.logger.info("Restarting MQTT task")
                    self._start_mqtt_task()

            # Sleep before checking again
            await asyncio.sleep(10)  # Check every 10 seconds


    def _setup_error_handlers(self):
        """Setup global error handlers"""

        def handle_exception(loop, context):
            exception = context.get('exception')
            message = context.get('message')
            task = context.get('task')

            if exception is None:
                self.logger.critical(f"Unhandled error: {message}")
            else:
                self.logger.critical(f"Unhandled exception in {task}: {str(exception)}", exc_info=exception)

            # If this is a critical task, try to restart the application
            is_critical = False
            if task and hasattr(task, 'get_name'):
                task_name = task.get_name()
                is_critical = any(critical_name in task_name for critical_name in ['main_loop', 'mqtt'])

            if is_critical and self.running:
                self.logger.warning("Critical task failed, attempting recovery")
                # Try to restart specific tasks based on context
                if self.mqtt_task and self.mqtt_task.done():
                    self._start_mqtt_task()

        loop = asyncio.get_event_loop()
        loop.set_exception_handler(handle_exception)


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
