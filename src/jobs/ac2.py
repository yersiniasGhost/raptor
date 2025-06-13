#!/usr/bin/env python3
"""
Actuator Stress Test Application
Performs stress testing on actuators with comprehensive data collection
"""

import asyncio
import json
import time
import csv
import statistics
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import threading
import signal
import sys

from actuator_manager import ActuatorManager  # Import your ActuatorManager
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
    target_speed: float
    position_error: float
    movement_time: float
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
    data_sample_rate: float = 0.1  # How often to sample data during movement
    position_tolerance: float = 2.0  # Acceptable position error
    current_limit: float = 10.0  # Max current draw alarm threshold
    speed_tolerance: float = 5.0  # Acceptable speed variation
    output_dir: str = "stress_test_results"
    config_file: str = "actuator_config.json"


class StressTestRunner:
    """Main stress test runner class"""



    def __init__(self, config: TestConfiguration):
        self.config = config
        self.logger = LogManager().get_logger("StressTestRunner")
        self.actuator_manager: Optional[ActuatorManager] = None
        self.test_data: List[TestMetrics] = []
        self.running = False
        self.start_time = None
        self.current_cycle = 0
        self.errors: List[str] = []
        self.lock = threading.Lock()

        # Setup output directory
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(exist_ok=True)

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
            self.logger.info("Initializing actuator manager...")
            self.actuator_manager = ActuatorManager.from_json(
                self.config.config_file,
                self.logger
            )

            # Verify actuators are responding
            actuator_ids = self.actuator_manager.get_slave_ids()
            if not actuator_ids:
                self.logger.error("No actuators found!")
                return False

            self.logger.info(f"Found {len(actuator_ids)} actuators: {actuator_ids}")

            # Test initial communication and setup each actuator
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

            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize actuators: {e}")
            return False



    async def collect_metrics(self, actuator_id: str, cycle: int,
                              target_pos: float, target_speed: float,
                              operation_type: str, start_time: float) -> List[TestMetrics]:
        """Collect metrics during actuator movement"""
        metrics = []
        actuator = self.actuator_manager.get_actuator(actuator_id)

        if not actuator:
            return metrics

        try:
            while self.running:
                current_time = time.time()

                # Get current actuator state using synchronous methods
                loop = asyncio.get_event_loop()

                # Run synchronous methods in executor to avoid blocking
                position = await loop.run_in_executor(None, actuator.get_position)
                if position is None:
                    await asyncio.sleep(self.config.data_sample_rate)
                    continue

                # Get current state (includes current, speed, voltage)
                state = await loop.run_in_executor(None, actuator.current_state)

                current = state.get('current', -90.0)
                speed = state.get('speed', -90.0)
                voltage = state.get('voltage', -90.0)

                # Calculate metrics
                position_error = abs(position - target_pos)
                movement_time = current_time - start_time

                metric = TestMetrics(
                    timestamp=current_time,
                    cycle_number=cycle,
                    actuator_id=actuator_id,
                    target_position=target_pos,
                    actual_position=position,
                    current_draw=current,
                    speed=speed,
                    target_speed=target_speed,
                    position_error=position_error,
                    movement_time=movement_time,
                    operation_type=operation_type
                )

                metrics.append(metric)

                # Check if we've reached target position
                if position_error <= self.config.position_tolerance:
                    self.logger.debug(f"Position reached for {actuator_id}: {position}")
                    break

                # Check for current overload (skip if invalid reading)
                if current > 0 and current > self.config.current_limit:
                    self.logger.warning(f"Current limit exceeded for {actuator_id}: {current}A")
                    self.errors.append(f"Cycle {cycle}: Current overload {actuator_id} - {current}A")

                # Check for errors using the error status
                error_status = await loop.run_in_executor(None, actuator.get_error_status)
                if error_status and any(vars(error_status).values()):
                    error_flags = [k for k, v in vars(error_status).items() if v]
                    self.logger.warning(f"Error flags detected for {actuator_id}: {error_flags}")
                    self.errors.append(f"Cycle {cycle}: Error flags {actuator_id} - {error_flags}")

                # Check motion status to see if still moving
                motion_status = await loop.run_in_executor(None, actuator.get_motion_status)
                if motion_status and not motion_status.IN_MOTION and position_error <= self.config.position_tolerance:
                    self.logger.debug(f"Motion stopped and position reached for {actuator_id}")
                    break

                await asyncio.sleep(self.config.data_sample_rate)

        except Exception as e:
            self.logger.error(f"Error collecting metrics for {actuator_id}: {e}")
            self.errors.append(f"Cycle {cycle}: Metrics collection error {actuator_id} - {str(e)}")

        return metrics



    async def wait_for_movement_complete(self, actuator_id: str, target_position: float,
                                         timeout: float = 60.0) -> bool:
        """Wait for actuator to complete movement and reach target position"""
        actuator = self.actuator_manager.get_actuator(actuator_id)
        if not actuator:
            return False

        start_time = time.time()
        loop = asyncio.get_event_loop()

        while time.time() - start_time < timeout:
            try:
                # Check position
                position = await loop.run_in_executor(None, actuator.get_position)
                if position is None:
                    await asyncio.sleep(0.1)
                    continue

                # Check if at target
                if abs(position - target_position) <= self.config.position_tolerance:
                    # Check if motion has stopped
                    motion_status = await loop.run_in_executor(None, actuator.get_motion_status)
                    if motion_status and not motion_status.IN_MOTION:
                        return True

                # Check for errors
                error_status = await loop.run_in_executor(None, actuator.get_error_status)
                if error_status and any(vars(error_status).values()):
                    error_flags = [k for k, v in vars(error_status).items() if v]
                    self.logger.error(f"Movement failed due to errors: {error_flags}")
                    return False

                await asyncio.sleep(0.2)

            except Exception as e:
                self.logger.error(f"Error waiting for movement completion: {e}")
                return False

        self.logger.warning(f"Movement timeout for {actuator_id}")
        return False



    async def perform_movement(self, target_position: float, target_speed: float,
                               operation_type: str, cycle: int) -> bool:
        """Perform a single movement operation"""
        try:
            actuator_ids = self.actuator_manager.get_slave_ids()
            start_time = time.time()

            self.logger.info(f"Cycle {cycle}: {operation_type} to {target_position} at {target_speed}")

            # Start movement - this will initiate the PDO-based movement
            success = await self.actuator_manager.move_multiple(target_position, target_speed)

            if not success:
                self.logger.error(f"Movement command failed for cycle {cycle}")
                self.errors.append(f"Cycle {cycle}: Movement command failed")
                return False

            # Start collecting metrics during movement for all actuators
            metric_tasks = []
            for actuator_id in actuator_ids:
                task = self.collect_metrics(
                    actuator_id, cycle, target_position,
                    target_speed, operation_type, start_time
                )
                metric_tasks.append(task)

            # Wait for movement to complete - the collect_metrics will stop when position is reached
            # But we also need to ensure the move_to() method has completed
            completion_tasks = []
            for actuator_id in actuator_ids:
                task = self.wait_for_movement_complete(actuator_id, target_position)
                completion_tasks.append(task)

            # Wait for both metrics collection and movement completion
            metrics_results, completion_results = await asyncio.gather(
                asyncio.gather(*metric_tasks),
                asyncio.gather(*completion_tasks),
                return_exceptions=True
            )

            # Check if movements completed successfully
            if isinstance(completion_results, list):
                if not all(completion_results):
                    self.logger.warning(f"Some actuators did not complete movement in cycle {cycle}")

            # Flatten and store metrics
            if isinstance(metrics_results, list):
                for actuator_metrics in metrics_results:
                    if isinstance(actuator_metrics, list):
                        with self.lock:
                            self.test_data.extend(actuator_metrics)

            # Dwell time - wait at position
            if self.config.dwell_time > 0:
                self.logger.debug(f"Dwelling for {self.config.dwell_time}s")
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

                    # Save intermediate results
                    await self.save_intermediate_results(cycle)

            self.logger.info("Stress test completed!")
            return True

        except Exception as e:
            self.logger.error(f"Stress test error: {e}")
            return False
        finally:
            self.running = False



    async def save_intermediate_results(self, cycle: int):
        """Save intermediate results during test"""
        try:
            filename = self.output_dir / f"intermediate_cycle_{cycle}.csv"
            await self.save_results_to_csv(filename)
        except Exception as e:
            self.logger.error(f"Failed to save intermediate results: {e}")



    async def save_results_to_csv(self, filename: Path = None):
        """Save test results to CSV file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.output_dir / f"stress_test_results_{timestamp}.csv"

        try:
            with open(filename, 'w', newline='') as csvfile:
                if not self.test_data:
                    self.logger.warning("No test data to save")
                    return

                fieldnames = list(asdict(self.test_data[0]).keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for metric in self.test_data:
                    writer.writerow(asdict(metric))

            self.logger.info(f"Results saved to {filename}")

        except Exception as e:
            self.logger.error(f"Failed to save results: {e}")



    def generate_summary_report(self) -> Dict:
        """Generate summary statistics"""
        if not self.test_data:
            return {}

        # Group data by actuator and operation type
        actuator_data = {}
        for metric in self.test_data:
            key = f"{metric.actuator_id}_{metric.operation_type}"
            if key not in actuator_data:
                actuator_data[key] = []
            actuator_data[key].append(metric)

        summary = {
            "test_duration": time.time() - self.start_time if self.start_time else 0,
            "total_cycles_attempted": self.current_cycle,
            "total_data_points": len(self.test_data),
            "errors": self.errors,
            "actuator_summary": {}
        }

        # Calculate statistics for each actuator/operation combination
        for key, data in actuator_data.items():
            if not data:
                continue

            positions = [d.actual_position for d in data]
            currents = [d.current_draw for d in data]
            speeds = [d.speed for d in data]
            errors = [d.position_error for d in data]
            times = [d.movement_time for d in data]

            summary["actuator_summary"][key] = {
                "data_points": len(data),
                "position_stats": {
                    "mean": statistics.mean(positions),
                    "min": min(positions),
                    "max": max(positions),
                    "std_dev": statistics.stdev(positions) if len(positions) > 1 else 0
                },
                "current_stats": {
                    "mean": statistics.mean(currents),
                    "min": min(currents),
                    "max": max(currents),
                    "std_dev": statistics.stdev(currents) if len(currents) > 1 else 0
                },
                "speed_stats": {
                    "mean": statistics.mean(speeds),
                    "min": min(speeds),
                    "max": max(speeds),
                    "std_dev": statistics.stdev(speeds) if len(speeds) > 1 else 0
                },
                "position_error_stats": {
                    "mean": statistics.mean(errors),
                    "min": min(errors),
                    "max": max(errors),
                    "std_dev": statistics.stdev(errors) if len(errors) > 1 else 0
                },
                "movement_time_stats": {
                    "mean": statistics.mean(times),
                    "min": min(times),
                    "max": max(times),
                    "std_dev": statistics.stdev(times) if len(times) > 1 else 0
                }
            }

        return summary



    async def save_summary_report(self, summary: Dict):
        """Save summary report to JSON file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.output_dir / f"stress_test_summary_{timestamp}.json"

            with open(filename, 'w') as f:
                json.dump(summary, f, indent=2, default=str)

            self.logger.info(f"Summary report saved to {filename}")

        except Exception as e:
            self.logger.error(f"Failed to save summary report: {e}")



    def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up resources...")
        if self.actuator_manager:
            self.actuator_manager.cleanup()


async def main():
    """Main application entry point"""

    # Configure test parameters
    config = TestConfiguration(
        cycles=500,
        extend_position=100.0,
        retract_position=0.0,
        extend_speed=50.0,
        retract_speed=50.0,
        dwell_time=1.0,
        data_sample_rate=0.1,
        position_tolerance=2.0,
        current_limit=10.0,
        speed_tolerance=5.0,
        output_dir="stress_test_results",
        config_file="actuator_config.json"
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

        # Save final results
        await test_runner.save_results_to_csv()

        # Generate and save summary report
        summary = test_runner.generate_summary_report()
        await test_runner.save_summary_report(summary)

        # Print summary to console
        print("\n" + "=" * 50)
        print("STRESS TEST SUMMARY")
        print("=" * 50)
        print(f"Test Duration: {summary.get('test_duration', 0):.2f} seconds")
        print(f"Cycles Completed: {summary.get('total_cycles_attempted', 0)}")
        print(f"Data Points Collected: {summary.get('total_data_points', 0)}")
        print(f"Errors: {len(summary.get('errors', []))}")

        if summary.get('errors'):
            print("\nErrors encountered:")
            for error in summary['errors'][:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(summary['errors']) > 10:
                print(f"  ... and {len(summary['errors']) - 10} more errors")

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