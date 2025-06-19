import subprocess
from utils.singleton import Singleton
from utils import LogManager

"""
Using a singleton to manage the state of all requested power on/off for the 5V power supply 
THIS IS TS-7180 ready only!
"""


class Power5V(metaclass=Singleton):
    def __init__(self):
        self.power_on_requests = 0
        self.logger = LogManager().get_logger("Power5V")

    def request_power_on(self):
        self.power_on_requests += 1
        self._power_on()

    def request_power_off(self):
        self.power_on_requests -= 1
        self._power_off()

    def _power_on(self):
        """Enable the 5V power supply for DIO outputs on the first time N =1 """
        if self.power_on_requests == 1:
            try:
                subprocess.run(["gpioset", "5", "16=1"], check=True)
                self.logger.info("5V power enabled")
                return True
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to enable 5V power: {e}")
                return False


    def _power_off(self):
        """Disable the 5V power supply"""
        if self.power_on_requests == 0:
            try:
                subprocess.run(["gpioset", "5", "16=0"], check=True)
                self.logger.info("5V power disabled")
                return True
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to disable 5V power: {e}")
                return False
