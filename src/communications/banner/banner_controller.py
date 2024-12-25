#!/usr/bin/python3
import subprocess
import time
import signal
import sys


class GPIOController:

    def __init__(self, chip_label="50004010.fpga_gpio", line_number=1):
        """Initialize GPIO controller using libgpiod commands

        Args:
            chip_label: The GPIO chip label (e.g., '50004010.fpga_gpio')
            line_number: The GPIO line number to control
        """
        self.chip_label = chip_label
        self.line_number = line_number
        self.verify_gpio()



    def verify_gpio(self):
        """Verify the GPIO chip exists and line is available"""
        try:
            # Check if GPIO chip exists
            result = subprocess.run(["gpiodetect"], capture_output=True, text=True)
            if self.chip_label not in result.stdout:
                raise Exception(f"GPIO chip {self.chip_label} not found")

            # Check if GPIO line is available
            result = subprocess.run(["gpioinfo", self.chip_label], capture_output=True, text=True)
            if "Device or resource busy" in result.stdout:
                raise Exception(f"GPIO line {self.line_number} is busy")

        except subprocess.CalledProcessError as e:
            raise Exception(f"Error verifying GPIO: {e}")



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
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error setting GPIO: {e}")
            return False



    def get_relay_state(self):
        """Get current relay state using gpioget

        Returns:
            Boolean indicating current state, or None on error
        """
        try:
            cmd = ["gpioget", self.chip_label, str(self.line_number)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip() == "1"
        except subprocess.CalledProcessError as e:
            print(f"Error getting GPIO state: {e}")
            return None



    def toggle_relay(self):
        """Toggle relay state"""
        current_state = self.get_relay_state()
        if current_state is not None:
            return self.set_relay(not current_state)
        return False


def signal_handler(signum, frame):
    """Handle cleanup on signal"""
    print("\nExiting...")
    if 'gpio' in globals():
        gpio.set_relay(False)  # Turn off relay on exit
    sys.exit(0)


if __name__ == "__main__":
    # Set up signal handlers for clean exit
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Initialize GPIO controller - using DIO header pin 1 (GPIO 1)
        gpio = GPIOController(chip_label="50004010.fpga_gpio", line_number=1)

        print(f"GPIO controller initialized for {gpio.chip_label} line {gpio.line_number}")
        print("Commands: on, off, toggle, status, quit")

        # Command loop
        while True:
            cmd = input("> ").lower().strip()

            if cmd == "on":
                if gpio.set_relay(True):
                    print("Relay turned on")
            elif cmd == "off":
                if gpio.set_relay(False):
                    print("Relay turned off")
            elif cmd == "toggle":
                if gpio.toggle_relay():
                    state = "on" if gpio.get_relay_state() else "off"
                    print(f"Relay toggled {state}")
            elif cmd == "status":
                state = gpio.get_relay_state()
                if state is not None:
                    print(f"Relay is {'on' if state else 'off'}")
            elif cmd in ["quit", "exit", "q"]:
                gpio.set_relay(False)  # Turn off relay before exit
                break
            else:
                print("Unknown command")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)