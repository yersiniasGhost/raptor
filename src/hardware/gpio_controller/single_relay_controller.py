import subprocess
import logging

logger = logging.getLogger(__name__)


class GPIOException(Exception):
    pass


class SingleRelayController:

    def __init__(self, dio_number: int = 1, polarity: str = "high"):
        """Initialize GPIO controller for TS-7180 DIO pins using libgpiod commands

        Args:
            dio_number: DIO number (1-7) corresponding to P3 connector pins
            polarity: The relay polarity - "high" means relay activates on HIGH signal,
                     "low" means relay activates on LOW signal
        """
        if dio_number < 1 or dio_number > 7:
            raise ValueError("DIO number must be between 1 and 7")

        self.dio_number = dio_number
        self.chip_number = 5  # FPGA GPIOs are on gpiochip5
        # DIO_1 through DIO_7 output control lines are at GPIO 22-28
        self.output_line = 21 + dio_number  # DIO_1=22, DIO_2=23, ..., DIO_7=28
        # DIO_1 through DIO_7 input reading lines are at GPIO 37-43
        self.input_line = 36 + dio_number  # DIO_1=37, DIO_2=38, ..., DIO_7=43

        self.current_state = False  # Track state internally
        self.polarity = polarity
        self.verify_gpio()
        # Ensure we start in OFF state
        self.set_relay(False)



    def verify_gpio(self):
        """Verify the GPIO chip exists"""
        try:
            # Check if GPIO chip exists
            result = subprocess.run(["gpiodetect"], capture_output=True, text=True, check=True)
            chip_name = f"gpiochip{self.chip_number}"
            if chip_name not in result.stdout:
                raise GPIOException(f"GPIO chip {chip_name} not found")
        except subprocess.CalledProcessError as e:
            raise GPIOException(f"Error running gpiodetect: {e}")
        except FileNotFoundError:
            raise GPIOException("gpiodetect command not found - libgpiod not installed?")



    def set_relay(self, state: bool) -> bool:
        """Set relay state using gpioset

        Args:
            state: Boolean, True for relay ON, False for relay OFF
        Returns:
            Boolean indicating success
        """
        try:
            # Determine the GPIO value based on desired state and polarity
            if self.polarity == "high":
                # High polarity: HIGH signal activates relay
                gpio_value = "1" if state else "0"
            else:  # low polarity
                # Low polarity: LOW signal activates relay
                gpio_value = "0" if state else "1"

            # Use gpioset with gpiochip and line number for TS-7180 DIO outputs
            cmd = ["gpioset", str(self.chip_number), f"{self.output_line}={gpio_value}"]
            subprocess.run(cmd, check=True)
            self.current_state = state  # Update internal state tracking
            logger.debug(f"Set DIO_{self.dio_number} to {'ON' if state else 'OFF'} (GPIO={gpio_value})")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Error setting DIO_{self.dio_number} (GPIO {self.chip_number}:{self.output_line}): {e}")
            return False
        except FileNotFoundError:
            logger.error("gpioset command not found - libgpiod not installed?")
            return False



    def get_relay_state(self) -> bool:
        """Get current relay state from internal tracking

        Returns:
            Boolean: True if relay is ON, False if OFF
        """
        return self.current_state



    def read_gpio_state(self) -> bool:
        """Read actual GPIO pin state and update internal tracking

        Returns:
            Boolean: True if GPIO reads high, False if low
        """
        try:
            # Read from the input line for DIO pins
            cmd = ["gpioget", str(self.chip_number), str(self.input_line)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            gpio_value = result.stdout.strip() == "1"

            # Update internal state based on polarity
            if self.polarity == "high":
                self.current_state = gpio_value
            else:
                self.current_state = not gpio_value

            return gpio_value

        except subprocess.CalledProcessError as e:
            logger.error(f"Error reading DIO_{self.dio_number} (GPIO {self.chip_number}:{self.input_line}): {e}")
            return False



    def toggle_relay(self) -> bool:
        """Toggle relay state

        Returns:
            Boolean indicating success
        """
        return self.set_relay(not self.current_state)



    def cleanup(self):
        """Cleanup - turn off relay"""
        self.set_relay(False)



    def __enter__(self):
        """Context manager entry"""
        return self



    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup"""
        self.cleanup()
