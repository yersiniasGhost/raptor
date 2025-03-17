import argparse
import asyncio
import time
from datetime import datetime
import os
import csv
import statistics
from typing import Dict, Union, Optional, Any, List
from database.db_utils import get_mqtt_config, get_telemetry_config, get_raptor_configuration
from database.database_manager import DatabaseManager
from utils import LogManager, EnvVars
from hardware.hardware_deployment import instantiate_hardware_from_dict, HardwareDeployment
from config.mqtt_config import MQTTConfig, FORMAT_FLAT, FORMAT_HIER, FORMAT_LINE_PROTOCOL
from config.telemetry_config import TelemetryConfig, MQTT_MODE, REST_MODE
from cloud.mqtt_comms import upload_telemetry_data_mqtt
from utils.system_status import collect_system_stats
if EnvVars().enable_simulators:
    from hardware.simulators.simulation_state import SimulationState


SUPPORTED_SYSTEMS = ["PV", "Meter", "BMS", "Converters", "IoT"]


class IoTController:

    def __init__(self, store_local: bool, simulator_mode: bool):
        # Setup logging with rotation and remote logging if needed
        self.logger = LogManager("iot_controller.log").get_logger("IoTController")
        self.running = True
        self.mqtt_config: MQTTConfig = get_mqtt_config(self.logger)
        self.telemetry_config: TelemetryConfig = get_telemetry_config(self.logger)
        self.telemetry_data: Optional[Dict[str, Any]] = None
        self.raptor_configuration = get_raptor_configuration(self.logger)
        self.store_local = store_local
        self.mqtt_task = None
        self.system_measurements = {}
        self.simulator = simulator_mode

        # Parameters for distributed sampling
        self.sample_count = max(1, self.telemetry_config.sampling)  # Ensure at least 1 sample
        self.averaging_method = self.telemetry_config.averaging_method

        self.logger.info(
            f"Initialized with {self.sample_count} samples per recording using {self.averaging_method} averaging (distributed throughout interval)")



    async def _take_synchronized_sample(self) -> dict:
        """
        Takes a single synchronized sample of all systems.
        This ensures all systems are measured at the same point in time.
        """
        db = DatabaseManager(EnvVars().db_path)
        system_measurements = {}

        # Setup all hardware objects first
        system_deployments = {}
        for system in SUPPORTED_SYSTEMS:
            hardware_deployments = {}
            for hardware in db.get_hardware_systems(system):
                deployment = instantiate_hardware_from_dict(hardware, self.logger)
                hardware_deployments[hardware["external_ref"]] = deployment
            system_deployments[system] = hardware_deployments

        # Now take measurements from all systems at once
        self.logger.info("Taking synchronized sample across all systems")
        if self.simulator:
            SimulationState().reset()
        for system, hardware_deployments in system_deployments.items():
            system_measurements[system] = {}
            for hardware_id, deployment in hardware_deployments.items():
                instance_data = deployment.data_acquisition()
                system_measurements[system][deployment.hardware_id] = instance_data
                if self.simulator:
                    SimulationState().add_state(system, deployment.hardware_id, instance_data)

        return system_measurements



    def _average_synchronized_samples(self, samples: List[dict]) -> dict:
        """
        Average multiple synchronized samples

        Args:
            samples: List of system measurements, each containing data for all systems

        Returns:
            A single dictionary with averaged values across all systems
        """
        if not samples:
            return {}

        # Create result structure
        result = {}

        # Get all systems from the first sample
        for system in samples[0].keys():
            result[system] = {}

            # Get all hardware IDs for this system in the first sample
            for hardware_id in samples[0][system].keys():
                result[system][hardware_id] = {}

                # Get all device IDs for this hardware in all samples
                all_device_ids = set()
                for sample in samples:
                    if system in sample and hardware_id in sample[system]:
                        all_device_ids.update(sample[system][hardware_id].keys())

                # Process each device ID
                for device_id in all_device_ids:
                    # Group data for this device across all samples
                    device_data_across_samples = []

                    for sample in samples:
                        if (system in sample and
                                hardware_id in sample[system] and
                                device_id in sample[system][hardware_id]):
                            device_data_across_samples.append(sample[system][hardware_id][device_id])

                    # If we have data for this device from at least one sample
                    if device_data_across_samples:
                        # Get all measurement keys
                        all_keys = set()
                        for device_data in device_data_across_samples:
                            all_keys.update(device_data.keys())

                        # Initialize device result
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
                                        # If no unique mode found, fall back to mean
                                        device_result[key] = statistics.mean(values)
                                else:
                                    # Default to mean if unknown method
                                    device_result[key] = statistics.mean(values)

                        # Add device result to result
                        result[system][hardware_id][device_id] = device_result

        return result



    def _format_telemetry_data(self, system_measurements: Dict[str, Any]) -> Dict[str, Any]:
        """ Format system measurements data for telemetry """
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
            self.logger.info(f"Line protocol: {len(lines)} lines collected.")
            return {"mode": FORMAT_LINE_PROTOCOL, "data": lines}
        else:
            return {}



    async def _upload_telemetry_data(self):
        if self.telemetry_config.mode == MQTT_MODE:
            upload_status = await upload_telemetry_data_mqtt(self.mqtt_config, self.telemetry_config, self.logger)
            self.logger.info(f"MQTT upload status: {upload_status}")
            return upload_status
        elif self.telemetry_config.mode == REST_MODE:
            self.logger.warning("REST mode NOT IMPLEMENTED")
            return True
        return False


    @staticmethod
    def _store_local_telemetry_data(system: str, data: dict):
        """
        Write data to CSV with timestamp
        data_list: List of tuples [(name, value)]
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for unit_id, data_list in data.items():
            if not len(data_list):
                continue
            filename = f"{system}_{unit_id}.csv"
            file_exists = os.path.exists(filename)
            with open(filename, 'a', newline='') as csvfile:
                fieldnames = ['Timestamp'] + sorted(list(data_list.keys()))
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                # Write header if file is new
                if not file_exists:
                    writer.writeheader()

                # Create row with timestamp and values
                row_data = {'Timestamp': timestamp}
                row_data.update({name: value for name, value in data_list.items()})
                writer.writerow(row_data)


    async def shutdown(self):
        self.logger.warning("SHUTDOWN")
        self.running = False
        DatabaseManager().close()



    async def main_loop(self):
        """
        Main execution loop with distributed sampling approach
        """
        self.logger.info(f"Starting up IoT Controller with distributed sampling.")
        interval_seconds = self.telemetry_config.interval

        self.logger.info(
            f"Using distributed sampling with {self.sample_count} samples over {interval_seconds}s intervals")
        sample_interval = interval_seconds / self.sample_count
        samples_collected = []
        next_sample_time = time.time()
        last_upload_attempt = 0
        upload_failure_count = 0
        max_upload_backoff = 300  # 5 minutes max between upload attempts

        while self.running:
            current_time = time.time()

            if current_time >= next_sample_time:
                try:
                    # Take a single synchronized sample of all systems
                    sample_data = await self._take_synchronized_sample()
                    samples_collected.append(sample_data)
                    self.logger.info(f"Collected synchronized sample {len(samples_collected)}/{self.sample_count}")

                    # Calculate next sample time
                    next_sample_time = next_sample_time + sample_interval

                    # If we've collected all samples, process them and reset
                    if len(samples_collected) >= self.sample_count:
                        # Average the samples
                        averaged_data = self._average_synchronized_samples(samples_collected)

                        # Store and upload the averaged data
                        self.system_measurements = averaged_data
                        self.telemetry_data = self._format_telemetry_data(averaged_data)

                        data = self.telemetry_data.get("data", [])
                        if data:
                            db = DatabaseManager(EnvVars().db_path)
                            db.store_telemetry_data(self.telemetry_data)

                            # Store locally if needed
                            if self.store_local:
                                for system, system_data in averaged_data.items():
                                    for hardware_id, hardware_data in system_data.items():
                                        self._store_local_telemetry_data(system, hardware_data)

                            # Determine if we should attempt an upload based on backoff strategy
                            should_attempt_upload = True
                            if upload_failure_count > 0:
                                time_since_last_upload = current_time - last_upload_attempt
                                backoff_time = min(2 ** upload_failure_count, max_upload_backoff)
                                should_attempt_upload = time_since_last_upload >= backoff_time

                                if not should_attempt_upload:
                                    self.logger.info(
                                        f"Skipping upload attempt due to previous failures. Next attempt in {backoff_time - time_since_last_upload:.1f}s")

                            # Upload to cloud if appropriate
                            if should_attempt_upload:
                                last_upload_attempt = current_time
                                upload_success = await self._upload_telemetry_data()

                                if upload_success:
                                    if upload_failure_count > 0:
                                        self.logger.info(
                                            f"Upload succeeded after {upload_failure_count} failed attempts")
                                        upload_failure_count = 0
                                    db.clear_telemetry_data()
                                else:
                                    upload_failure_count += 1
                                    backoff_time = min(2 ** upload_failure_count, max_upload_backoff)
                                    if upload_failure_count == 1:
                                        self.logger.warning(
                                            f"Failed to upload telemetry data. Will retry in {backoff_time}s")
                                    elif upload_failure_count % 10 == 0:  # Log only periodically to reduce spam
                                        self.logger.error(
                                            f"Still unable to upload telemetry data after {upload_failure_count} attempts. Next retry in {backoff_time}s")

                        # Try to collect system stats
                        try:
                            sbc_state = {0: collect_system_stats()}
                            self._store_local_telemetry_data("RAPTOR", sbc_state)
                        except Exception as e:
                            self.logger.error("Failed to perform system status acquisition", exc_info=True)

                        # Reset for next cycle
                        samples_collected = []
                        self.logger.info(
                            f"Completed full sampling cycle, next cycle starts at {datetime.fromtimestamp(next_sample_time)}")

                    # Small sleep to avoid tight loop
                    await asyncio.sleep(0.1)

                except Exception as e:
                    self.logger.critical(f"Critical error in distributed sampling: {str(e)}", exc_info=True)
                    # Skip this sample but continue with the next one
                    next_sample_time = current_time + sample_interval
                    await asyncio.sleep(1)  # Brief pause before continuing
            else:
                # Sleep until close to the next sample time
                sleep_time = min(next_sample_time - current_time, 1.0)  # Check at least every second
                await asyncio.sleep(sleep_time)


    async def main_loop_orig(self):
        """
        Main execution loop with distributed sampling approach
        """
        self.logger.info(f"Starting up IoT Controller with distributed sampling.")
        interval_seconds = self.telemetry_config.interval

        self.logger.info(
            f"Using distributed sampling with {self.sample_count} samples over {interval_seconds}s intervals")
        sample_interval = interval_seconds / self.sample_count
        samples_collected = []
        next_sample_time = time.time()

        while self.running:
            current_time = time.time()

            if current_time >= next_sample_time:
                try:
                    # Take a single synchronized sample of all systems
                    sample_data = await self._take_synchronized_sample()
                    samples_collected.append(sample_data)
                    self.logger.info(f"Collected synchronized sample {len(samples_collected)}/{self.sample_count}")

                    # Calculate next sample time
                    next_sample_time = next_sample_time + sample_interval

                    # If we've collected all samples, process them and reset
                    if len(samples_collected) >= self.sample_count:
                        # Average the samples
                        averaged_data = self._average_synchronized_samples(samples_collected)

                        # Store and upload the averaged data
                        self.system_measurements = averaged_data
                        self.telemetry_data = self._format_telemetry_data(averaged_data)

                        data = self.telemetry_data.get("data", [])
                        if data:
                            db = DatabaseManager(EnvVars().db_path)
                            db.store_telemetry_data(self.telemetry_data)

                            # Store locally if needed
                            if self.store_local:
                                for system, system_data in averaged_data.items():
                                    for hardware_id, hardware_data in system_data.items():
                                        self._store_local_telemetry_data(system, hardware_data)

                            # Upload to cloud
                            upload_success = await self._upload_telemetry_data()
                            if upload_success:
                                db.clear_telemetry_data()
                            else:
                                self.logger.error("Wasn't able to upload telemetry data.")

                        # Try to collect system stats
                        try:
                            sbc_state = {0: collect_system_stats()}
                            self._store_local_telemetry_data("RAPTOR", sbc_state)
                        except Exception as e:
                            self.logger.error("Failed to perform system status acquisition", exc_info=True)

                        # Reset for next cycle
                        samples_collected = []
                        self.logger.info(
                            f"Completed full sampling cycle, next cycle starts at {datetime.fromtimestamp(next_sample_time)}")

                    # Small sleep to avoid tight loop
                    await asyncio.sleep(0.1)

                except Exception as e:
                    self.logger.critical(f"Critical error in distributed sampling: {str(e)}", exc_info=True)
                    # Skip this sample but continue with the next one
                    next_sample_time = current_time + sample_interval
                    await asyncio.sleep(1)  # Brief pause before continuing
            else:
                # Sleep until close to the next sample time
                sleep_time = min(next_sample_time - current_time, 1.0)  # Check at least every second
                await asyncio.sleep(sleep_time)


def parse_args():
    parser = argparse.ArgumentParser(description='IoT controller for data acquisition and upload')
    parser.add_argument('-l', '--local', action="store_true", default=True,
                        help="Stores the data in local CSV files for debugging")
    parser.add_argument('-s', '--simulator', action="store_true", default=False,
                        help="Sets the simulator mode so that intermediate measurements form systems are accessible")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    controller = IoTController(store_local=args.local, simulator_mode=args.simulator)
    asyncio.run(controller.main_loop())
