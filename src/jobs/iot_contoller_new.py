#!/usr/bin/env python3
"""
Example of how to refactor the IoT Controller to use the utility components
"""

import asyncio
import time
import statistics
from datetime import datetime
from typing import Dict, Union, Optional, Any, List

from database.db_utils import get_mqtt_config, get_telemetry_config, get_raptor_configuration
from database.database_manager import DatabaseManager
from utils import LogManager, EnvVars
from hardware.hardware_deployment import instantiate_hardware_from_dict, HardwareDeployment
from config.mqtt_config import MQTTConfig, FORMAT_FLAT, FORMAT_HIER, FORMAT_LINE_PROTOCOL
from config.telemetry_config import TelemetryConfig, MQTT_MODE, REST_MODE
from cloud.mqtt_comms import upload_telemetry_data_mqtt
from utils.system_status import collect_system_stats

# Import our new utility components
from utils.telemetry_formatter import TelemetryFormatter, create_system_telemetry_points
from utils.data_logger_base import BaseDataLogger, LoggerConfig, TelemetryUploadManager

if EnvVars().enable_simulators:
    from hardware.simulators.simulation_state import SimulationState

SUPPORTED_SYSTEMS = ["PV", "Meter", "BMS", "Converters", "IoT", "Charge Controller", "Generation"]


class IoTDataLogger(BaseDataLogger):
    """
    Specialized data logger for IoT system data
    """



    def __init__(self, config: LoggerConfig, logger,
                 telemetry_formatter: Optional[TelemetryFormatter] = None,
                 simulator_mode: bool = False):
        super().__init__(config, logger, telemetry_formatter)
        self.simulator_mode = simulator_mode
        self.system_deployments = {}
        self._setup_hardware()



    def _setup_hardware(self):
        """Setup all hardware deployments"""
        db = DatabaseManager(EnvVars().db_path)

        for system in SUPPORTED_SYSTEMS:
            hardware_deployments = {}
            for hardware in db.get_hardware_systems(system):
                deployment = instantiate_hardware_from_dict(hardware, self.logger)
                hardware_deployments[hardware["external_ref"]] = deployment
            self.system_deployments[system] = hardware_deployments



    def get_data_sources(self) -> List[str]:
        """Return list of system names as data sources"""
        return list(self.system_deployments.keys())



    def get_csv_fieldnames(self) -> List[str]:
        """Return CSV fieldnames for IoT system data"""
        return [
            'timestamp', 'system', 'hardware_id', 'device_id',
            'measurement_key', 'measurement_value'
        ]



    def collect_data_point(self, system_name: str) -> Optional[Dict[str, Any]]:
        """Collect data from all hardware in a specific system"""
        try:
            if self.simulator_mode:
                SimulationState().reset()

            system_data = {}
            hardware_deployments = self.system_deployments.get(system_name, {})

            self.logger.debug(f"Reading system: {system_name}")

            for hardware_id, deployment in hardware_deployments.items():
                try:
                    instance_data = deployment.data_acquisition()
                    system_data[deployment.hardware_id] = instance_data

                    if self.simulator_mode:
                        SimulationState().add_state(system_name, deployment.hardware_id, instance_data)

                except Exception as e:
                    self.logger.error(f"Unable to read from: {system_name}/{hardware_id}, continuing")

            # Flatten the data for CSV logging
            flattened_data = []
            timestamp = int(time.time())

            for hardware_id, hardware_data in system_data.items():
                for device_id, device_data in hardware_data.items():
                    for key, value in device_data.items():
                        flattened_data.append({
                            'timestamp': timestamp,
                            'system': system_name,
                            'hardware_id': hardware_id,
                            'device_id': device_id,
                            'measurement_key': key,
                            'measurement_value': value
                        })

            return {
                'raw_data': system_data,
                'flattened': flattened_data,
                'timestamp': timestamp
            }

        except Exception as e:
            self.logger.error(f"Error collecting data from system {system_name}: {e}")
            return None



    def _convert_to_telemetry_points(self, source_id: str, data_points: List[Dict[str, Any]]):
        """Convert IoT data points to TelemetryPoint objects"""
        telemetry_points = []

        for data_point in data_points:
            if 'raw_data' in data_point:
                # Convert the raw system data to telemetry points
                system_measurements = {source_id: data_point['raw_data']}
                points = create_system_telemetry_points(system_measurements)
                telemetry_points.extend(points)

        return telemetry_points


class IoTController:
    """
    Refactored IoT Controller using utility components
    """



    def __init__(self, store_local: bool, simulator_mode: bool):
        # Setup logging
        self.logger = LogManager("iot-controller.log").get_logger("IoTController")
        self.running = True

        # Configuration
        self.mqtt_config: MQTTConfig = get_mqtt_config(self.logger)
        self.telemetry_config: TelemetryConfig = get_telemetry_config(self.logger)
        self.raptor_configuration = get_raptor_configuration(self.logger)
        self.store_local = store_local
        self.simulator_mode = simulator_mode

        # Parameters for distributed sampling
        self.sample_count = max(1, self.telemetry_config.sampling)
        self.averaging_method = self.telemetry_config.averaging_method

        # Setup telemetry components
        self.telemetry_formatter = TelemetryFormatter(
            raptor_id=self.raptor_configuration.raptor_id,
            format_type=self.mqtt_config.format
        )

        # Setup data logger
        logger_config = LoggerConfig(
            output_dir="iot_data_logs",
            sample_rate=self.telemetry_config.interval / self.sample_count,
            buffer_size=2000,
            csv_flush_interval=10.0,
            enable_telemetry=True,
            telemetry_batch_size=200
        )

        self.data_logger = IoTDataLogger(
            config=logger_config,
            logger=self.logger,
            telemetry_formatter=self.telemetry_formatter,
            simulator_mode=simulator_mode
        )

        # Setup telemetry upload manager
        self.telemetry_upload_manager = TelemetryUploadManager(
            upload_function=self._upload_telemetry_batch,
            logger=self.logger,
            batch_size=100
        )

        self.logger.info(
            f"Initialized with {self.sample_count} samples per recording using {self.averaging_method} averaging"
        )



    async def _upload_telemetry_batch(self, telemetry_points) -> bool:
        """Upload telemetry batch"""
        try:
            # Format the data
            formatted_data = self.telemetry_formatter.format_telemetry_data(telemetry_points)

            # Store in database temporarily
            db = DatabaseManager(EnvVars().db_path)
            db.store_telemetry_data(formatted_data)

            # Upload based on configured mode
            if self.telemetry_config.mode == MQTT_MODE:
                success = await upload_telemetry_data_mqtt(self.mqtt_config, self.telemetry_config, self.logger)
                if success:
                    db.clear_telemetry_data()
                return success
            elif self.telemetry_config.mode == REST_MODE:
                self.logger.warning("REST mode NOT IMPLEMENTED")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Error uploading telemetry batch: {e}")
            return False



    def _average_synchronized_samples(self, samples: List[Dict]) -> Dict:
        """
        Average multiple synchronized samples using the utility data logger
        """
        if not samples:
            return {}

        # Extract raw data from samples
        all_system_measurements = []
        for sample in samples:
            system_measurements = {}
            for system_name, sample_data in sample.items():
                if isinstance(sample_data, dict) and 'raw_data' in sample_data:
                    system_measurements[system_name] = sample_data['raw_data']
            if system_measurements:
                all_system_measurements.append(system_measurements)

        if not all_system_measurements:
            return {}

        # Average the measurements
        result = {}

        # Get all systems from the first sample
        for system in all_system_measurements[0].keys():
            result[system] = {}

            # Get all hardware IDs for this system
            for hardware_id in all_system_measurements[0][system].keys():
                result[system][hardware_id] = {}

                # Get all device IDs across all samples
                all_device_ids = set()
                for sample in all_system_measurements:
                    if system in sample and hardware_id in sample[system]:
                        all_device_ids.update(sample[system][hardware_id].keys())

                # Process each device ID
                for device_id in all_device_ids:
                    device_data_across_samples = []

                    for sample in all_system_measurements:
                        if (system in sample and
                                hardware_id in sample[system] and
                                device_id in sample[system][hardware_id]):
                            device_data_across_samples.append(sample[system][hardware_id][device_id])

                    if device_data_across_samples:
                        # Get all measurement keys
                        all_keys = set()
                        for device_data in device_data_across_samples:
                            all_keys.update(device_data.keys())

                        device_result = {}

                        # Process each measurement key
                        for key in all_keys:
                            values = []
                            for device_data in device_data_across_samples:
                                if key in device_data and isinstance(device_data[key], (int, float)):
                                    values.append(device_data[key])

                            # Calculate average if we have values
                            if values:
                                if self.averaging_method == "mean":
                                    device_result[key] = statistics.mean(values)
                                elif self.averaging_method == "median":
                                    device_result[key] = statistics.median(values)
                                elif self.averaging_method == "mode":
                                    try:
                                        device_result[key] = statistics.mode(values)
                                    except statistics.StatisticsError:
                                        device_result[key] = statistics.mean(values)
                                else:
                                    device_result[key] = statistics.mean(values)

                        result[system][hardware_id][device_id] = device_result

        return result



    async def _take_synchronized_sample(self) -> Dict:
        """Take a synchronized sample using the data logger"""
        sample_data = {}

        for system_name in self.data_logger.get_data_sources():
            data_point = self.data_logger.collect_data_point(system_name)
            if data_point:
                sample_data[system_name] = data_point

        return sample_data



    @staticmethod
    def _store_local_telemetry_data(system: str, data: dict):
        """Store data locally in CSV format"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for unit_id, data_list in data.items():
            if not len(data_list):
                continue
            filename = f"{system}_{unit_id}.csv"
            file_exists = Path(filename).exists()
            data_names = sorted(list(data_list.keys()))

            with open(filename, 'a', newline='') as csvfile:
                fieldnames = ['Timestamp'] + data_names
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                if not file_exists:
                    writer.writeheader()

                row_data = {'Timestamp': timestamp}
                for name in data_names:
                    row_data[name] = data_list[name]
                writer.writerow(row_data)



    async def shutdown(self):
        """Shutdown the controller"""
        self.logger.warning("SHUTDOWN")
        self.running = False

        if self.data_logger:
            self.data_logger.stop_logging()

        if self.telemetry_upload_manager:
            self.telemetry_upload_manager.stop_upload_manager()

        DatabaseManager().close()



    async def main_loop(self):
        """
        Main execution loop with distributed sampling approach using utility components
        """
        self.logger.info("Starting up IoT Controller with utility components.")
        interval_seconds = self.telemetry_config.interval

        # Start the data logger
        self.data_logger.start_logging()

        # Start telemetry upload manager
        self.telemetry_upload_manager.start_upload_manager()

        sample_interval = interval_seconds / self.sample_count
        samples_collected = []
        next_sample_time = time.time()
        last_upload_attempt = 0
        upload_failure_count = 0
        max_upload_backoff = 300

        self.logger.info(
            f"Using distributed sampling with {self.sample_count} samples over {interval_seconds}s intervals"
        )

        while self.running:
            current_time = time.time()

            if current_time >= next_sample_time:
                try:
                    # Take a synchronized sample
                    sample_data = await self._take_synchronized_sample()
                    samples_collected.append(sample_data)
                    self.logger.info(f"Collected synchronized sample {len(samples_collected)}/{self.sample_count}")

                    next_sample_time = next_sample_time + sample_interval

                    # Process complete sample set
                    if len(samples_collected) >= self.sample_count:
                        # Average the samples
                        averaged_data = self._average_synchronized_samples(samples_collected)

                        # Store locally if requested
                        if self.store_local:
                            for system, system_data in averaged_data.items():
                                for hardware_id, hardware_data in system_data.items():
                                    self._store_local_telemetry_data(system, hardware_data)

                        # Upload telemetry via the upload manager
                        should_attempt_upload = True
                        if upload_failure_count > 0:
                            time_since_last_upload = current_time - last_upload_attempt
                            backoff_time = min(2 ** upload_failure_count, max_upload_backoff)
                            should_attempt_upload = time_since_last_upload >= backoff_time

                        if should_attempt_upload:
                            last_upload_attempt = current_time

                            # Get telemetry batch from data logger
                            telemetry_points = self.data_logger.get_telemetry_batch(max_points=200)

                            if telemetry_points:
                                # Queue for upload
                                self.telemetry_upload_manager.queue_telemetry_batch(telemetry_points)

                                # Clear the buffers
                                self.data_logger.clear_telemetry_buffers()

                                self.logger.info(f"Queued {len(telemetry_points)} telemetry points for upload")
                                upload_failure_count = 0
                            else:
                                upload_failure_count += 1

                        # Try to collect system stats
                        try:
                            self.logger.info("Collecting system status")
                            sbc_state = {0: collect_system_stats()}
                            self.logger.info(sbc_state)
                            self._store_local_telemetry_data("RAPTOR", sbc_state)
                        except Exception as e:
                            self.logger.error("Failed to perform system status acquisition", exc_info=True)

                        # Reset for next cycle
                        samples_collected = []
                        self.logger.info(
                            f"Completed full sampling cycle, next cycle starts at {datetime.fromtimestamp(next_sample_time)}")

                    await asyncio.sleep(0.1)

                except Exception as e:
                    self.logger.critical(f"Critical error in distributed sampling: {str(e)}", exc_info=True)
                    next_sample_time = current_time + sample_interval
                    await asyncio.sleep(1)
            else:
                sleep_time = min(next_sample_time - current_time, 1.0)
                await asyncio.sleep(sleep_time)


def parse_args():
    import argparse
    parser = argparse.ArgumentParser(description='IoT controller using utility components')
    parser.add_argument('-l', '--local', action="store_true", default=True,
                        help="Store data in local CSV files for debugging")
    parser.add_argument('-s', '--simulator', action="store_true", default=False,
                        help="Enable simulator mode")
    return parser.parse_args()


if __name__ == "__main__":
    import csv
    from pathlib import Path

    args = parse_args()
    controller = IoTController(store_local=args.local, simulator_mode=args.simulator)
    asyncio.run(controller.main_loop())