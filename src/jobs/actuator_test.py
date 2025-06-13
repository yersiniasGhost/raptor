#!/usr/bin/env python3
"""
Actuator Stress Test Application
Performs stress testing on actuators with comprehensive data collection
"""

import asyncio
import time
import csv
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import threading
import signal
import sys
import queue
from utils.envvars import EnvVars
from database.database_manager import DatabaseManager

from hardware.electrak.actuator_manager import ActuatorManager
from utils import LogManager


@dataclass
class TestMetrics:
    """Data structure for test metrics"""
    timestamp: float
    cycle_number: int
    actuator_id: str
    target_position: float
    actual_position: float
    current_draw: float
    speed: float
    voltage: float
    target_speed: float
    position_error: float
    error_flags: str
    motion_in_progress: bool
    operation_type: str  # 'extend' or 'retract'


@dataclass
class TestConfiguration:
    """Test configuration parameters"""
    cycles: int = 500
    extend_position: float = 100.0
    retract_position: float = 0.0
    extend_speed: float = 50.0
    retract_speed: float = 50.0
    dwell_time: float = 1.0  # Time to wait at each position
    data_sample_rate: float = 1.0  # How often to sample data during movement
    position_tolerance: float = 2.0  # Acceptable position error
    current_limit: float = 10.0  # Max current draw alarm threshold
    speed_tolerance: float = 5.0  # Acceptable speed variation
    movement_timeout: float = 120.0
    output_dir: str = "stress_test_results"
    config_file: str = "actuator_config.json"


class ContinuousDataLogger:
    """Handles continuous data logging in separate threads"""



    def __init__(self, actuator_manager: ActuatorManager, config: TestConfiguration):
        self.actuator_manager = actuator_manager
        self.config = config
        self.logger = LogManager().get_logger("DataLogger")
        self.running = False
        self.data_threads = []
        self.file_writers = {}
        self.csv_files = {}
        self.current_cycle = 0
        self.current_operation = "idle"
        self.target_position = 0.0
        self.target_speed = 0.0
        self.data_lock = threading.Lock()

        # Setup output directory
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Create timestamp for this test run
        self.test_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")



    def start_logging(self):
        """Start continuous data logging for all actuators"""
        self.running = True
        actuator_ids = self.actuator_manager.get_slave_ids()

        for actuator_id in actuator_ids:
            # Create CSV file for this actuator
            filename = self.output_dir / f"actuator_{actuator_id}_{self.test_timestamp}.csv"
            csv_file = open(filename, 'w', newline='')

            fieldnames = list(asdict(TestMetrics(
                timestamp=0, cycle_number=0, actuator_id="", target_position=0,
                actual_position=0, current_draw=0, speed=0, voltage=0,
                target_speed=0, position_error=0, operation_type="",
                motion_in_progress=False, error_flags=""
            )).keys())

            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            csv_file.flush()

            self.csv_files[actuator_id] = csv_file
            self.file_writers[actuator_id] = writer

            # Start data collection thread for this actuator
            thread = threading.Thread(
                target=self._data_collection_thread,
                args=(actuator_id,),
                daemon=True,
                name=f"DataLogger-{actuator_id}"
            )
            thread.start()
            self.data_threads.append(thread)

            self.logger.info(f"Started data logging for actuator {actuator_id}")



    def _data_collection_thread(self, actuator_id: str):
        """Continuous data collection thread for a single actuator"""
        actuator = self.actuator_manager.get_actuator(actuator_id)
        if not actuator:
            self.logger.error(f"Could not get actuator {actuator_id}")
            return

        self.logger.info(f"Data collection thread started for {actuator_id}")

        while self.running:
            try:
                start_time = time.time()

                # Get current state
                position = actuator.get_position()
                state = actuator.current_state()

                current = state.get('current', -90.0)
                speed = state.get('speed', -90.0)
                voltage = state.get('voltage', -90.0)

                # Get motion status
                motion_status = actuator.get_motion_status()
                in_motion = motion_status.IN_MOTION if motion_status else False

                # Get error status
                error_status = actuator.get_error_status()
                error_flags = ""
                if error_status:
                    active_errors = [k for k, v in vars(error_status).items() if v]
                    error_flags = ",".join(active_errors) if active_errors else ""

                # Calculate position error
                with self.data_lock:
                    current_target = self.target_position
                    current_target_speed = self.target_speed
                    current_cycle = self.current_cycle
                    current_op = self.current_operation

                position_error = abs(position - current_target) if position is not None else -1.0

                # Create metrics record
                metric = TestMetrics(
                    timestamp=time.time(),
                    cycle_number=current_cycle,
                    actuator_id=actuator_id,
                    target_position=current_target,
                    actual_position=position if position is not None else -90.0,
                    current_draw=current,
                    speed=speed,
                    voltage=voltage,
                    target_speed=current_target_speed,
                    position_error=position_error,
                    operation_type=current_op,
                    motion_in_progress=in_motion,
                    error_flags=error_flags
                )

                # Write to CSV file
                with self.data_lock:
                    if actuator_id in self.file_writers:
                        self.file_writers[actuator_id].writerow(asdict(metric))
                        self.csv_files[actuator_id].flush()

                # Maintain sampling rate
                elapsed = time.time() - start_time
                sleep_time = max(0, self.config.data_sample_rate - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

            except Exception as e:
                self.logger.error(f"Data collection error for {actuator_id}: {e}")
                time.sleep(self.config.data_sample_rate)



    def update_test_state(self, cycle: int, operation: str, target_pos: float, target_speed: float):
        """Update the current test state for data logging"""
        with self.data_lock:
            self.current_cycle = cycle
            self.current_operation = operation
            self.target_position = target_pos
            self.target_speed = target_speed



    def stop_logging(self):
        """Stop data logging and close files"""
        self.logger.info("Stopping data logging...")
        self.running = False

        # Wait for threads to finish
        for thread in self.data_threads:
            thread.join(timeout=2.0)

        # Close CSV files
        for csv_file in self.csv_files.values():
            csv_file.close()

        self.logger.info("Data logging stopped and files closed")


class StressTestRunner:
    """Main stress test runner class"""



    def __init__(self, config: TestConfiguration):
        self.config = config
        self.logger = LogManager("actuator_stress_test.log").get_logger("StressTestRunner")
        self.actuator_manager: Optional[ActuatorManager] = None
        self.data_logger: Optional[ContinuousDataLogger] = None
        self.running = False
        self.start_time = None
        self.current_cycle = 0
        self.errors: List[str] = []

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)



    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, stopping test...")
        self.running = False



    def initialize_actuators(self) -> bool:
        """Initialize the actuator manager"""
        try:
            db = DatabaseManager(EnvVars().db_path)
            for hardware in db.get_hardware_systems("Actuators"):
                self.logger.info(f"Adding Actuators")
                self.logger.info(f"TOD: {hardware}")
                try:
                    self.actuator_manager = ActuatorManager.from_dict(hardware, self.logger)
                except Exception as e:
                    self.logger.error(f"Failed to load ActuatorManager, {e}")
                    self.actuator_manager = None

            # Verify actuators are responding
            actuator_ids = self.actuator_manager.get_slave_ids()
            if not actuator_ids:
                self.logger.error("No actuators found!")
                return False

            self.logger.info(f"Found {len(actuator_ids)} actuators: {actuator_ids}")

            # Test initial communication
            for actuator_id in actuator_ids:
                actuator = self.actuator_manager.get_actuator(actuator_id)
                if not actuator:
                    self.logger.error(f"Failed to get actuator {actuator_id}")
                    return False

                # Ensure actuator is properly setup
                try:
                    actuator.setup()
                    # Test basic communication
                    position = actuator.get_position()
                    if position is None:
                        self.logger.warning(f"Could not read initial position for {actuator_id}")
                    else:
                        self.logger.info(f"Actuator {actuator_id} initial position: {position}mm")

                    # Check for any initial errors
                    error_status = actuator.get_error_status()
                    if error_status and any(vars(error_status).values()):
                        error_flags = [k for k, v in vars(error_status).items() if v]
                        self.logger.warning(f"Initial errors on {actuator_id}: {error_flags}")
                        # Try to clear errors
                        if actuator.clear_errors():
                            self.logger.info(f"Cleared initial errors for {actuator_id}")
                        else:
                            self.logger.error(f"Failed to clear initial errors for {actuator_id}")
                            return False

                except Exception as e:
                    self.logger.error(f"Failed to setup actuator {actuator_id}: {e}")
                    return False

            # Initialize data logger
            self.data_logger = ContinuousDataLogger(self.actuator_manager, self.config)

            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize actuators: {e}")
            return False



    async def wait_for_movement_complete(self, target_position: float, timeout: float = None) -> bool:
        """Wait for all actuators to complete movement and reach target position"""
        if timeout is None:
            timeout = self.config.movement_timeout

        actuator_ids = self.actuator_manager.get_slave_ids()
        start_time = time.time()

        while time.time() - start_time < timeout:
            if not self.running:
                return False

            all_complete = True

            for actuator_id in actuator_ids:
                actuator = self.actuator_manager.get_actuator(actuator_id)
                if not actuator:
                    continue

                try:
                    # Check position
                    position = actuator.get_position()
                    if position is None:
                        all_complete = False
                        continue

                    # Check if at target
                    if abs(position - target_position) > self.config.position_tolerance:
                        all_complete = False
                        continue

                    # Check if motion has stopped
                    motion_status = actuator.get_motion_status()
                    if motion_status and motion_status.IN_MOTION:
                        all_complete = False
                        continue

                    # Check for errors
                    error_status = actuator.get_error_status()
                    if error_status and any(vars(error_status).values()):
                        error_flags = [k for k, v in vars(error_status).items() if v]
                        self.logger.error(f"Movement failed due to errors on {actuator_id}: {error_flags}")
                        self.errors.append(f"Cycle {self.current_cycle}: Errors on {actuator_id} - {error_flags}")
                        return False

                except Exception as e:
                    self.logger.error(f"Error checking movement status for {actuator_id}: {e}")
                    all_complete = False
                    continue

            if all_complete:
                return True

            await asyncio.sleep(0.2)

        self.logger.warning(f"Movement timeout after {timeout}s")
        return False



    async def perform_movement(self, target_position: float, target_speed: float,
                               operation_type: str, cycle: int) -> bool:
        """Perform a single movement operation"""
        try:
            self.logger.info(f"Cycle {cycle}: {operation_type} to {target_position} at {target_speed}")

            # Update data logger with current test state
            self.data_logger.update_test_state(cycle, operation_type, target_position, target_speed)

            # Start movement
            success = await self.actuator_manager.move_multiple(target_position, target_speed)

            if not success:
                self.logger.error(f"Movement command failed for cycle {cycle}")
                self.errors.append(f"Cycle {cycle}: Movement command failed")
                return False

            # Wait for movement to complete
            success = await self.wait_for_movement_complete(target_position)

            if not success:
                self.logger.error(f"Movement did not complete properly for cycle {cycle}")
                self.errors.append(f"Cycle {cycle}: Movement completion failed")
                return False

            # Dwell time - wait at position
            if self.config.dwell_time > 0:
                self.logger.debug(f"Dwelling for {self.config.dwell_time}s")
                self.data_logger.update_test_state(cycle, f"{operation_type}_dwell", target_position, 0)
                await asyncio.sleep(self.config.dwell_time)

            return True

        except Exception as e:
            self.logger.error(f"Movement error in cycle {cycle}: {e}")
            self.errors.append(f"Cycle {cycle}: Movement exception - {str(e)}")
            return False



    async def run_stress_test(self) -> bool:
        """Run the complete stress test"""
        self.logger.info("Starting stress test...")
        self.running = True
        self.start_time = time.time()

        # Start continuous data logging
        self.data_logger.start_logging()

        try:
            for cycle in range(1, self.config.cycles + 1):
                if not self.running:
                    self.logger.info("Test stopped by user")
                    break

                self.current_cycle = cycle

                # Extend movement
                success = await self.perform_movement(
                    self.config.extend_position,
                    self.config.extend_speed,
                    "extend",
                    cycle
                )

                if not success and self.running:
                    self.logger.error(f"Extend failed in cycle {cycle}")
                    continue

                if not self.running:
                    break

                # Retract movement
                success = await self.perform_movement(
                    self.config.retract_position,
                    self.config.retract_speed,
                    "retract",
                    cycle
                )

                if not success and self.running:
                    self.logger.error(f"Retract failed in cycle {cycle}")
                    continue

                # Progress update
                if cycle % 10 == 0:
                    elapsed = time.time() - self.start_time
                    self.logger.info(f"Completed {cycle}/{self.config.cycles} cycles "
                                     f"in {elapsed:.1f}s")

            self.logger.info("Stress test completed!")
            return True

        except Exception as e:
            self.logger.error(f"Stress test error: {e}")
            return False
        finally:
            self.running = False
            # Stop data logging
            if self.data_logger:
                self.data_logger.stop_logging()



    def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up resources...")
        self.running = False

        if self.data_logger:
            self.data_logger.stop_logging()

        if self.actuator_manager:
            self.actuator_manager.cleanup()


async def main():
    """Main application entry point"""

    # Configure test parameters
    config = TestConfiguration(
        cycles=500,
        extend_position=100.0,
        retract_position=80.0,
        extend_speed=100.0,
        retract_speed=100.0,
        dwell_time=1.0,
        data_sample_rate=1.0,
        position_tolerance=2.0,
        current_limit=20.0,
        speed_tolerance=5.0,
        output_dir="/root/raptor/tests/stress_test_results",
        config_file="/root/raptor/data/ElectrakActuators/electrak_deployment.json"
    )

    # Create test runner
    test_runner = StressTestRunner(config)

    try:
        # Initialize actuators
        if not test_runner.initialize_actuators():
            print("Failed to initialize actuators!")
            return 1

        # Run stress test
        success = await test_runner.run_stress_test()

        # Print summary to console
        print("\n" + "=" * 50)
        print("STRESS TEST SUMMARY")
        print("=" * 50)
        elapsed = time.time() - test_runner.start_time if test_runner.start_time else 0
        print(f"Test Duration: {elapsed:.2f} seconds")
        print(f"Cycles Completed: {test_runner.current_cycle}")
        print(f"Errors: {len(test_runner.errors)}")

        if test_runner.errors:
            print("\nErrors encountered:")
            for error in test_runner.errors[:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(test_runner.errors) > 10:
                print(f"  ... and {len(test_runner.errors) - 10} more errors")

        print(f"\nData files saved to: {config.output_dir}/")
        print("Each actuator has its own CSV file with continuous measurements.")

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        return 1
    except Exception as e:
        print(f"Test failed with error: {e}")
        return 1
    finally:
        test_runner.cleanup()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)