from typing import List, Tuple
import psutil
import time
import subprocess
import os
from database.database_manager import DatabaseManager
from utils import LogManager
from utils import Singleton

"""
Using a singleton to manage the state of all requested power on/off for the 5V power supply 
THIS IS TS-7180 ready only!
"""


class Power5V(metaclass=Singleton):

    def __init__(self):
        self.logger = LogManager().get_logger("Power5V")



    def log_current_power_state(self):
        """Log current power state and active requests"""
        try:
            active_requests, dead_pids = self.get_process_states()
            request_count = len(active_requests)
            power_state = Power5V().check_state()

            if request_count > 0:
                self.logger.info(f"Power state: {power_state}, Active requests: {request_count}, PIDs: {active_requests}")
                self.logger.info(f"Number of dead pids: {len(dead_pids)}, {dead_pids}")
            else:
                self.logger.debug(f"Power state: {power_state}, No active requests")

        except Exception as e:
            self.logger.error(f"Error logging current state: {e}")



    def request_power_on(self, process_id: int = None):
        """Request power on for a specific process ID"""
        if process_id is None:
            process_id = os.getpid()

        db = DatabaseManager()
        is_first_request = db.add_power_request(process_id)
        self.logger.info(f"Request power ON for PID {process_id}. First request: {is_first_request}")

        if is_first_request:
            self._power_on()



    def request_power_off(self, process_id: int = None):
        """Request power off for a specific process ID"""
        if process_id is None:
            process_id = os.getpid()

        db = DatabaseManager()
        is_last_request = db.remove_power_request(process_id)
        self.logger.info(f"Request power OFF for PID {process_id}. Last request: {is_last_request}")

        if is_last_request:
            self._power_off()

    def get_process_states(self) -> Tuple[List[int], List[int]]:
        """Remove power requests for processes that are no longer running"""
        db = DatabaseManager()
        active_pids = db.get_power_requests()
        dead_pids = []
        for pid in active_pids:
            try:
                # Check if process exists and is running
                if not psutil.pid_exists(pid):
                    dead_pids.append(pid)
                else:
                    # Double-check the process is actually running
                    process = psutil.Process(pid)
                    if process.status() == psutil.STATUS_ZOMBIE:
                        dead_pids.append(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process doesn't exist or we can't access it
                dead_pids.append(pid)
        return active_pids, dead_pids


    def cleanup_dead_processes(self):
        active_pids, dead_pids = self.get_process_states()
        for pid in dead_pids:
            self.logger.info(f"Cleaning up dead process PID {pid}")
            # This will check if it's the last request and turn off power if needed
            self.request_power_off(pid)
        return dead_pids

    def _power_on(self):
        """Enable the 5V power supply for DIO outputs"""
        try:
            subprocess.run(["gpioset", "5", "16=1"], check=True)
            self.logger.info("5V power enabled")
            time.sleep(0.1)
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to enable 5V power: {e}")
            return False



    def _power_off(self):
        """Disable the 5V power supply"""
        try:
            subprocess.run(["gpioset", "5", "16=0"], check=True)
            self.logger.info("5V power disabled")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to disable 5V power: {e}")
            return False



    def check_state(self):
        try:
            result = subprocess.run(
                ['gpioget', '5', '16'],
                check=True,
                capture_output=True,
                text=True
            )

            # gpioget returns '0' or '1' followed by newline
            gpio_state = result.stdout.strip()
            self.logger.info(result)
            state = "ON" if gpio_state == "1" else "OFF"
            return state

        except subprocess.CalledProcessError as e:
            self.logger.error("Cannot ready state")
            raise subprocess.CalledProcessError(
                e.returncode,
                e.cmd,
                f"Failed to read GPIO state: {e.stderr.strip()}"
            )