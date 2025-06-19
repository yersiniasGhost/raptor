#!/usr/bin/env python3
"""
Simple TS-7180 Relay Control Demo Application

This app demonstrates basic relay control using the SingleRelayController class.
It provides a menu-driven interface to control relays connected to DIO pins.
"""

import time
import logging
import subprocess
from hardware.power_5v.power_5v import Power5V
from single_relay_controller import SingleRelayController, GPIOException

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RelayDemoApp:

    def __init__(self):
        self.relays = {}
        self.power_enabled = False

    def enable_5v_power(self):
        Power5V().request_power_on()
        self.power_enabled = True


    def disable_5v_power(self):
        Power5V().request_power_off()
        self.power_enabled = False


    def setup_relay(self, dio_number, polarity="high"):
        """Setup a relay controller for a specific DIO pin"""
        try:
            if not self.power_enabled:
                print("Warning: 5V power is not enabled. Enabling now...")
                if not self.enable_5v_power():
                    print("Failed to enable 5V power!")
                    return False

            relay = SingleRelayController(dio_number=dio_number, polarity=polarity)
            self.relays[dio_number] = relay
            logger.info(f"Relay controller setup for DIO_{dio_number}")
            return True
        except GPIOException as e:
            logger.error(f"Failed to setup relay on DIO_{dio_number}: {e}")
            return False



    def control_relay(self, dio_number, state):
        """Control a specific relay"""
        if dio_number not in self.relays:
            print(f"Relay on DIO_{dio_number} not setup. Setting up now...")
            if not self.setup_relay(dio_number):
                return False

        relay = self.relays[dio_number]
        success = relay.set_relay(state)
        if success:
            state_str = "ON" if state else "OFF"
            print(f"Relay on DIO_{dio_number} turned {state_str}")
        else:
            print(f"Failed to control relay on DIO_{dio_number}")
        return success



    def toggle_relay(self, dio_number):
        """Toggle a specific relay"""
        if dio_number not in self.relays:
            print(f"Relay on DIO_{dio_number} not setup. Setting up now...")
            if not self.setup_relay(dio_number):
                return False

        relay = self.relays[dio_number]
        success = relay.toggle_relay()
        if success:
            state_str = "ON" if relay.get_relay_state() else "OFF"
            print(f"Relay on DIO_{dio_number} toggled to {state_str}")
        else:
            print(f"Failed to toggle relay on DIO_{dio_number}")
        return success



    def show_status(self):
        """Show current status of all relays"""
        print("\n=== Relay Status ===")
        print(f"5V Power: {'ENABLED' if self.power_enabled else 'DISABLED'}")

        if not self.relays:
            print("No relays configured")
            return

        for dio_num, relay in self.relays.items():
            state = "ON" if relay.get_relay_state() else "OFF"
            print(f"DIO_{dio_num}: {state} (polarity: {relay.polarity})")



    def sequence_demo(self):
        """Run a demonstration sequence with multiple relays"""
        print("\n=== Running Relay Sequence Demo ===")

        # Setup relays on DIO 1, 2, 3
        demo_dios = [1, 2, 3]
        for dio in demo_dios:
            if not self.setup_relay(dio):
                print(f"Failed to setup DIO_{dio}, skipping sequence demo")
                return

        print("Turning on relays in sequence...")
        for dio in demo_dios:
            self.control_relay(dio, True)
            time.sleep(1)

        time.sleep(2)

        print("Turning off relays in reverse sequence...")
        for dio in reversed(demo_dios):
            self.control_relay(dio, False)
            time.sleep(1)

        print("Sequence demo complete!")



    def cleanup(self):
        """Clean up all relays and disable power"""
        print("\n=== Cleaning up ===")
        for dio_num, relay in self.relays.items():
            relay.set_relay(False)
            print(f"DIO_{dio_num} turned OFF")

        if self.power_enabled:
            self.disable_5v_power()



    def show_menu(self):
        """Display the main menu"""
        print("\n=== TS-7180 Relay Control Demo ===")
        print("1. Setup relay on DIO pin")
        print("2. Turn relay ON")
        print("3. Turn relay OFF")
        print("4. Toggle relay")
        print("5. Show relay status")
        print("6. Run sequence demo")
        print("7. Enable/Disable 5V power")
        print("8. Cleanup and exit")
        print("9. Exit without cleanup")



    def run(self):
        """Main application loop"""
        print("TS-7180 Relay Control Demo Application")
        print("=" * 40)

        try:
            while True:
                self.show_menu()
                choice = input("\nEnter choice (1-9): ").strip()

                if choice == "1":
                    try:
                        dio_num = int(input("Enter DIO number (1-7): "))
                        if dio_num < 1 or dio_num > 7:
                            print("Invalid DIO number. Must be 1-7.")
                            continue

                        polarity = input("Enter polarity (high/low) [high]: ").strip().lower()
                        if not polarity:
                            polarity = "high"

                        if polarity not in ["high", "low"]:
                            print("Invalid polarity. Must be 'high' or 'low'.")
                            continue

                        self.setup_relay(dio_num, polarity)
                    except ValueError:
                        print("Invalid input. Please enter a number.")

                elif choice == "2":
                    try:
                        dio_num = int(input("Enter DIO number to turn ON: "))
                        self.control_relay(dio_num, True)
                    except ValueError:
                        print("Invalid input. Please enter a number.")

                elif choice == "3":
                    try:
                        dio_num = int(input("Enter DIO number to turn OFF: "))
                        self.control_relay(dio_num, False)
                    except ValueError:
                        print("Invalid input. Please enter a number.")

                elif choice == "4":
                    try:
                        dio_num = int(input("Enter DIO number to toggle: "))
                        self.toggle_relay(dio_num)
                    except ValueError:
                        print("Invalid input. Please enter a number.")

                elif choice == "5":
                    self.show_status()

                elif choice == "6":
                    self.sequence_demo()

                elif choice == "7":
                    if self.power_enabled:
                        print("5V power is currently ENABLED")
                        if input("Disable 5V power? (y/N): ").strip().lower() == 'y':
                            self.disable_5v_power()
                    else:
                        print("5V power is currently DISABLED")
                        if input("Enable 5V power? (y/N): ").strip().lower() == 'y':
                            self.enable_5v_power()

                elif choice == "8":
                    self.cleanup()
                    break

                elif choice == "9":
                    print("Exiting without cleanup...")
                    break

                else:
                    print("Invalid choice. Please enter 1-9.")

        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Cleaning up...")
            self.cleanup()
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            self.cleanup()


if __name__ == "__main__":
    app = RelayDemoApp()
    app.run()