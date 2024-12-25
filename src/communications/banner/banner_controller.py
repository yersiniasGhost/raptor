#!/usr/bin/python3
import os
import sys
import time
import signal


class FPGAGPIOController:

    def __init__(self):
        self.gpio_chip = "50004010.fpga_gpio"
        self.gpio_line = "1"  # IO 1
        self.gpio_path = f"/sys/class/gpio/gpiochip{self.gpio_chip}/gpio{self.gpio_line}"
        self.setup_gpio()



    def setup_gpio(self):
        """Setup FPGA GPIO pin for output"""
        # Export GPIO if not already exported
        if not os.path.exists(self.gpio_path):
            export_path = "/sys/class/gpio/export"
            try:
                with open(export_path, "w") as f:
                    f.write(f"{self.gpio_chip}{self.gpio_line}")
                time.sleep(0.1)  # Wait for system to create gpio files
            except Exception as e:
                print(f"Error exporting GPIO: {e}")
                sys.exit(1)

        # Set direction to output
        try:
            with open(f"{self.gpio_path}/direction", "w") as f:
                f.write("out")
        except Exception as e:
            print(f"Error setting GPIO direction: {e}")
            sys.exit(1)



    def cleanup(self):
        """Cleanup GPIO on program exit"""
        try:
            with open("/sys/class/gpio/unexport", "w") as f:
                f.write(f"{self.gpio_chip}{self.gpio_line}")
        except Exception as e:
            print(f"Error cleaning up GPIO: {e}")



    def set_relay(self, state):
        """Set relay state (True for on, False for off)"""
        try:
            with open(f"{self.gpio_path}/value", "w") as f:
                f.write("1" if state else "0")
            return True
        except Exception as e:
            print(f"Error setting relay: {e}")
            return False



    def toggle_relay(self):
        """Toggle relay state"""
        try:
            with open(f"{self.gpio_path}/value", "r") as f:
                current_state = int(f.read().strip())
            return self.set_relay(not current_state)
        except Exception as e:
            print(f"Error toggling relay: {e}")
            return False


def signal_handler(signum, frame):
    """Handle cleanup on signal"""
    print("\nCleaning up...")
    if 'gpio' in globals():
        gpio.cleanup()
    sys.exit(0)


if __name__ == "__main__":
    # Set up signal handlers for clean exit
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Initialize GPIO controller
        gpio = FPGAGPIOController()

        print("FPGA GPIO controller initialized")
        print("Commands: on, off, toggle, quit")

        # Simple command loop
        while True:
            cmd = input("> ").lower().strip()

            if cmd == "on":
                gpio.set_relay(True)
                print("Relay turned on")
            elif cmd == "off":
                gpio.set_relay(False)
                print("Relay turned off")
            elif cmd == "toggle":
                if gpio.toggle_relay():
                    print("Relay toggled")
            elif cmd in ["quit", "exit", "q"]:
                break
            else:
                print("Unknown command")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        gpio.cleanup()