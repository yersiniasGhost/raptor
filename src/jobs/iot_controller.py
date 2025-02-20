import asyncio
from typing import Dict, Any, Optional
from database.db_utils import get_mqtt_config
from database.database_manager import DatabaseManager
from utils import LogManager, EnvVars
from hardware.hardware_deployment import instantiate_hardware_from_dict, HardwareDeployment
from cloud.mqtt_config import MQTTConfig


class IoTController:

    def __init__(self):
        # Setup logging with rotation and remote logging if needed
        self.running = True
        self._setup_error_handlers()
        self.logger = LogManager().get_logger(__name__)
        self.mqtt_config: MQTTConfig = get_mqtt_config(self.logger)


    async def query_device(self, device_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Query a single IoT device with retries and error handling"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        device_config['url'],
                        timeout=device_config.get('timeout', 10)
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    self.logger.debug(f"Successfully queried device {device_config['id']}")
                    return data
        except Exception as e:
            self.logger.error(
                f"Error querying device {device_config['id']}: {str(e)}",
                exc_info=True
            )
            raise



    #@backoff.on_exception(
        #backoff.expo,
        #Exception,
        #max_tries=3
    #)
    async def upload_to_cloud(self, data: Dict[str, Any]) -> bool:
        """Upload data to cloud with retries"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        self.config['cloud_endpoint'],
                        json=data,
                        headers=self.config.get('cloud_headers', {})
                ) as response:
                    response.raise_for_status()
                    self.logger.info("Successfully uploaded data to cloud")
                    return True
        except Exception as e:
            self.logger.error(f"Cloud upload error: {str(e)}", exc_info=True)
            raise



    async def check_schedule_updates(self) -> None:
        """Check for schedule updates from cloud"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{self.config['cloud_endpoint']}/schedule"
                ) as response:
                    if response.status == 200:
                        new_schedule = await response.json()
                        self._update_schedule(new_schedule)
        except Exception as e:
            self.logger.error(f"Schedule update check failed: {str(e)}")
            # Continue with existing schedule


    def _data_acquisition(self):
        db = DatabaseManager(EnvVars().db_path)
        telemetry_data = {}
        for system in ["BMS", "Converters"]:
            for hardware in db.get_hardware_systems(system):
                self.logger.info(f"ACQ: {hardware['driver_path']}")
                deployment: HardwareDeployment = instantiate_hardware_from_dict(hardware)
                instance_telemetry_data = deployment.data_acquisition(self.mqtt_config.format)
                print("DATA", instance_telemetry_data)
                telemetry_data = telemetry_data | instance_telemetry_data
        print(telemetry_data)


    async def main_loop(self):
        """  Main execution loop
             This IoT controller is responsible for executing on a schedule a set of actions:
             a) Data Acquisition:  Read BMS, Converter data, (do we need actuator status?)
             b) Upload to the cloud
             c) Download any instructions from the cloud and act on them
             d) Check new telemetry schedule and update timer.
        """
        while self.running:
            try:
                self._data_acquisition()
                # Check for schedule updates
                # await self.check_schedule_updates()

                # Get all BMS hardware definitions from SQLite

                #

                device_data = {}
                for device in self.config['devices']:
                    try:
                        data = await self.query_device(device)
                        if data:
                            device_data[device['id']] = data
                    except Exception as e:
                        self.logger.error(f"Device query failed for {device['id']}: {str(e)}")
                        # Continue with other devices

                # Store data locally first
                try:
                    with self.db_connection() as conn:
                        self._store_data(conn, device_data)
                except Exception as e:
                    self.logger.error(f"Local storage failed: {str(e)}")

                # Upload to cloud if we have any data
                if device_data:
                    await self.upload_to_cloud(device_data)

                # Wait for next interval
                await asyncio.sleep(self.config['query_interval'])

            except Exception as e:
                self.logger.critical(f"Critical error in main loop: {str(e)}", exc_info=True)
                # Implement alert mechanism here (email, SMS, etc.)
                await asyncio.sleep(60)  # Wait before retrying



    def _setup_error_handlers(self):
        """Setup global error handlers"""

        def handle_exception(loop, context):
            exception = context.get('exception', context['message'])
            self.logger.critical(f"Unhandled error: {str(exception)}", exc_info=True)
            # Implement alert mechanism here
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(handle_exception)



if __name__ == "__main__":

    controller = IoTController()
    controller._data_acquisition()
    # asyncio.run(controller.main_loop())
