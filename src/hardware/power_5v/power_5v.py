import time
import subprocess
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

    def request_power_on(self):
        db = DatabaseManager()
        requests = db.power_on()
        self.logger.info(f"Request power ON.  Power on requests: {requests}")
        # self.logger.info(self.check_state())
        self._power_on(requests)
        # self.logger.info(self.check_state())


    def request_power_off(self):
        db = DatabaseManager()
        requests = db.power_off()
        self.logger.info(f"Request power OFF.  Remaining requests: {requests}")
        # self.logger.info(self.check_state())
        self._power_off(requests)
        # self.logger.info(self.check_state())



    def _power_on(self, requests: int):
        """Enable the 5V power supply for DIO outputs on the first time N =1 """
        if requests == 1:
            try:
                subprocess.run(["gpioset", "5", "16=1"], check=True)
                self.logger.info("5V power enabled")
                time.sleep(0.1)
                return True
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to enable 5V power: {e}")
                return False


    def _power_off(self, requests: int):
        """Disable the 5V power supply"""
        if requests == 0:
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
