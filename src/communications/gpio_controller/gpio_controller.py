import subprocess
import logging

logger = logging.getLogger(__name__)


class GPIOException(Exception):
    pass


class GPIOController:

    def __init__(self, chip_label="50004010.fpga_gpio", line_number=1):
        """Initialize GPIO controller using libgpiod commands

        Args:
            chip_label: The GPIO chip label (e.g., '50004010.fpga_gpio')
            line_number: The GPIO line number to control
        """
        self.chip_label = chip_label
        self.line_number = line_number
        self.current_state = False  # Track state internally
        self.verify_gpio()
        # Ensure we start in OFF state
        self.set_relay(False)



    def verify_gpio(self):
        """Verify the GPIO chip exists"""
        try:
            # Check if GPIO chip exists
            result = subprocess.run(["gpiodetect"], capture_output=True, text=True)
            if self.chip_label not in result.stdout:
                raise GPIOException(f"GPIO chip {self.chip_label} not found")

        except subprocess.CalledProcessError as e:
            raise GPIOException(f"Error verifying GPIO: {e}")



    def set_relay(self, state):
        """Set relay state using gpioset

        Args:
            state: Boolean, True for on, False for off
        Returns:
            Boolean indicating success
        """
        try:
            value = "1" if state else "0"
            cmd = ["gpioset", self.chip_label, f"{self.line_number}={value}"]
            subprocess.run(cmd, check=True)
            self.current_state = state  # Update internal state tracking
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error setting GPIO: {e}")
            return False



    def get_relay_state(self):
        """Get current relay state from internal tracking

        Returns:
            Boolean indicating current state
        """
        return self.current_state



    def toggle_relay(self):
        """Toggle relay state"""
        return self.set_relay(not self.current_state)
