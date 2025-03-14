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

SUPPORTED_SYSTEMS = ["BMS", "Converters", "PV"]


class IoTController:

    def __init__(self, store_local: bool, sample_count: int = 1, averaging_method: str = "mean",
                 distributed_sampling: bool = True):
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

        # New parameters for multiple measurements
        self.sample_count = sample_count
        self.averaging_method = averaging_method
        self.distributed_sampling = distributed_sampling

        sampling_type = "distributed throughout interval" if distributed_sampling else "rapid succession"
        self.logger.info(
            f"Initialized with {sample_count} samples per recording using {averaging_method} averaging ({sampling_type})")



    async def _data_acquisition(self) -> dict:
        """
        Read the data only. Holds data in a dictionary (internal format)
        For non-distributed sampling, if sample_count > 1, takes multiple measurements and averages them
        """
        db = DatabaseManager(EnvVars().db_path)
        sz = 0
        system_measurements = {}

        for system in SUPPORTED_SYSTEMS:
            hardware_measurements = {}
            for hardware in db.get_hardware_systems(system):
                deployment: HardwareDeployment = instantiate_hardware_from_dict(hardware, self.logger)
                self.logger.info(f"ACQ: System: {system} / {hardware['driver_path']} / {hardware['external_ref']}")

                # For non-distributed sampling, take multiple measurements if sample_count > 1
                if not self.distributed_sampling and self.sample_count > 1:
                    instance_data_samples = []
                    for i in range(self.sample_count):
                        sample_data = deployment.data_acquisition()
                        instance_data_samples.append(sample_data)
                        if i < self.sample_count - 1:  # Don't sleep after the last sample
                            await asyncio.sleep(0.5)  # Small delay between samples

                    # Average the samples
                    instance_data = self._average_measurements(instance_data_samples)
                    self.logger.info(f"Averaged {self.sample_count} samples using {self.averaging_method} method")
                else:
                    # Single measurement
                    instance_data = deployment.data_acquisition()

                sz += len(instance_data)

                # Only store locally if not in distributed mode (otherwise it will be stored after averaging)
                if self.store_local and not (self.distributed_sampling and self.sample_count > 1):
                    self._store_local_telemetry_data(system, instance_data)

                hardware_measurements[deployment.hardware_id] = instance_data
                self.logger.debug(f"DATA acq: {instance_data}")
            system_measurements[system] = hardware_measurements

        self.system_measurements = system_measurements
        self.logger.info(f"Data acq: collected from {sz} devices.")
        return system_measurements



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
        for system, hardware_deployments in system_deployments.items():
            system_measurements[system] = {}
            for hardware_id, deployment in hardware_deployments.items():
                instance_data = deployment.data_acquisition()
                system_measurements[system][deployment.hardware_id] = instance_data

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



    def _average_measurements(self, samples: List[Dict[int, Dict[str, Union[float, int]]]]) -> Dict[int, Dict[str, Union[float, int]]]:
        """
        Average multiple measurements based on the selected method

        Args:
            samples: List of measurements, where each measurement is a dictionary of device_id to values

        Returns:
            A single dictionary with averaged values
        """
        result = {}

        # Check if we have any samples
        if not samples:
            return result

        # Get all device IDs from the first sample
        for device_id in samples[0].keys():
            result[device_id] = {}

            # Get all measurement keys for this device from the first sample
            if device_id in samples[0]:
                for key in samples[0][device_id].keys():
                    # Collect all values for this key across all samples
                    values = []
                    for sample in samples:
                        if device_id in sample and key in sample[device_id]:
                            value = sample[device_id][key]
                            if isinstance(value, (int, float)):
                                values.append(value)

                    # Calculate the average based on the specified method
                    if values:
                        if self.averaging_method == "mean":
                            result[device_id][key] = statistics.mean(values)
                        elif self.averaging_method == "median":
                            result[device_id][key] = statistics.median(values)
                        elif self.averaging_method == "mode":
                            try:
                                result[device_id][key] = statistics.mode(values)
                            except statistics.StatisticsError:
                                # If no unique mode found, fall back to mean
                                result[device_id][key] = statistics.mean(values)
                        else:
                            # Default to mean if unknown method
                            result[device_id][key] = statistics.mean(values)

        return result



    def _average_system_measurements(self, system_samples: List[
        Dict[str, Dict[str, Dict[int, Dict[str, Union[float, int]]]]]]) -> Dict[
        str, Dict[str, Dict[int, Dict[str, Union[float, int]]]]]:
        """
        Average multiple system measurements for distributed sampling

        Args:
            system_samples: List of system measurements, each containing nested dictionaries by system, hardware, device_id

        Returns:
            A single averaged system measurement dictionary
        """
        result = {}

        # Check if we have any samples
        if not system_samples:
            return result

        # Get all systems from the first sample
        for system in system_samples[0].keys():
            result[system] = {}

            # Get all hardware IDs for this system
            for hardware_id in system_samples[0][system].keys():
                result[system][hardware_id] = {}

                # Collect all device_ids across all samples for this hardware
                all_device_ids = set()
                for sample in system_samples:
                    if system in sample and hardware_id in sample[system]:
                        all_device_ids.update(sample[system][hardware_id].keys())

                # For each device_id, average the readings
                for device_id in all_device_ids:
                    # Collect all readings for this device across samples
                    device_samples = []
                    for sample in system_samples:
                        if system in sample and hardware_id in sample[system] and device_id in sample[system][hardware_id]:
                            device_samples.append(sample[system][hardware_id][device_id])

                    # Average these device readings
                    if device_samples:
                        device_dict = {}

                        # Get all measurement keys
                        all_keys = set()
                        for device_sample in device_samples:
                            all_keys.update(device_sample.keys())

                        # For each measurement key, collect and average values
                        for key in all_keys:
                            values = []
                            for device_sample in device_samples:
                                if key in device_sample:
                                    value = device_sample[key]
                                    if isinstance(value, (int, float)):
                                        values.append(value)

                            # Calculate average based on the specified method
                            if values:
                                if self.averaging_method == "mean":
                                    device_dict[key] = statistics.mean(values)
                                elif self.averaging_method == "median":
                                    device_dict[key] = statistics.median(values)
                                elif self.averaging_method == "mode":
                                    try:
                                        device_dict[key] = statistics.mode(values)
                                    except statistics.StatisticsError:
                                        # If no unique mode found, fall back to mean
                                        device_dict[key] = statistics.mean(values)
                                else:
                                    # Default to mean if unknown method
                                    device_dict[key] = statistics.mean(values)

                        # Add the averaged device data to the result
                        result[system][hardware_id][device_id] = device_dict

        return result



    async def _data_acquisition_non_distributed(self):
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

                            # Add number of samples as a tag if more than 1
                            # if self.sample_count > 1:
                            #     tags.append(f"samples={self.sample_count}")
                            #     tags.append(f"method={self.averaging_method}")

                            fields = [f"{point}={value}" for point, value in m_data.items()]
                            tag_str = ','.join(tags)
                            field_str = ','.join(fields)
                            line = f"{measurement},{tag_str} {field_str} {timestamp}"
                            lines.append(line)
            self.logger.info(f"Line protocol:  {len(lines)} lines collected.")
            return {"mode": FORMAT_LINE_PROTOCOL, "data": lines}
        else:
            return {}



    def _format_telemetry(self, inst_data: Dict[str, Dict[str, Union[float, int]]],
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
            # Add sampling info if more than 1 sample
            # if self.sample_count > 1:
            #     tags.append(f"samples={self.sample_count}")
            #     tags.append(f"method={self.averaging_method}")

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
            filename = f"{system}_{slave_id}.csv"
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

        # For distributed sampling
        if self.distributed_sampling and self.sample_count > 1:
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
                                        self._store_local_telemetry_data(system, system_data)

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

        # Original non-distributed approach
        else:
            while self.running:
                start = time.time()
                try:
                    await self._data_acquisition_non_distributed()

                    # Wait for next interval
                    elapsed = time.time() - start
                    sleep_time = max(0, interval_seconds - elapsed)

                    # Sleep for the remaining time
                    await asyncio.sleep(sleep_time)

                except Exception as e:
                    self.logger.critical(f"Critical error in main loop: {str(e)}", exc_info=True)
                    # Implement alert mechanism here (email, SMS, etc.)
                    elapsed = time.time() - start
                    sleep_time = max(min(interval_seconds, 30),
                                     interval_seconds - elapsed)  # Cap error retry to 30 seconds
                    await asyncio.sleep(sleep_time)  # Wait before retrying


def parse_args():
    parser = argparse.ArgumentParser(description='IoT controller is the long running process that does data'
                                                 ' acquisition, data upload and command processing')
    parser.add_argument('-l', '--local', action="store_true",
                        help="Stores the data in local CSV files for debugging")
    parser.add_argument('-n', '--samples', type=int, default=1,
                        help="Number of samples to take for each measurement (default: 1)")
    parser.add_argument('-m', '--method', type=str, default="mean", choices=["mean", "median", "mode"],
                        help="Method to use for averaging multiple samples (default: mean)")
    parser.add_argument('-d', '--distributed', action="store_true", default=True,
                        help="Use distributed sampling across the interval (default: True)")
    parser.add_argument('-r', '--rapid', action="store_true",
                        help="Use rapid sampling instead of distributed sampling")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    # If rapid flag is set, override distributed setting
    distributed_sampling = not args.rapid if args.samples > 1 else False

    controller = IoTController(
        store_local=args.local,
        sample_count=args.samples,
        averaging_method=args.method,
        distributed_sampling=distributed_sampling
    )
    asyncio.run(controller.main_loop())


# Example messages's:
# mosquitto_pub -h localhost -t "raptors/67b672097fc4a4b18476b1ed/messages" -m '{"action":"firmware_update", "params": {"tag":"2025-03-03-lf-influxdb"}}'