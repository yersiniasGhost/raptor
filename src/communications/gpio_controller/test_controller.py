import sys
import signal
from .banner_controller import MultiRelayController


def signal_handler(signum, frame):
    """Handle cleanup on signal"""
    print("\nExiting...")
    if 'controller' in globals():
        controller.cleanup()
    sys.exit(0)


if __name__ == "__main__":
    # Set up signal handlers for clean exit
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        controller = MultiRelayController()

        print("Multi-relay controller initialized")
        print("Commands:")
        print("  on <relay>    - Turn on specific relay (red/yellow/green) or 'all'")
        print("  off <relay>   - Turn off specific relay (red/yellow/green) or 'all'")
        print("  toggle <relay> - Toggle specific relay (red/yellow/green)")
        print("  status        - Show status of all relays")
        print("  quit          - Exit program")

        while True:
            cmd = input("> ").lower().strip()
            parts = cmd.split()

            if not parts:
                continue

            if parts[0] == "quit":
                controller.cleanup()
                break

            elif parts[0] == "status":
                status = controller.get_status_all()
                for name, state in status.items():
                    print(f"{name}: {'on' if state else 'off'}")

            elif len(parts) == 2:
                command, relay = parts

                if relay == "all" and command in ["on", "off"]:
                    state = command == "on"
                    if controller.set_all(state):
                        print(f"All relays turned {command}")

                elif relay in controller.relays:
                    if command == "on":
                        if controller.relays[relay].set_relay(True):
                            print(f"{relay} relay turned on")
                    elif command == "off":
                        if controller.relays[relay].set_relay(False):
                            print(f"{relay} relay turned off")
                    elif command == "toggle":
                        if controller.relays[relay].toggle_relay():
                            state = "on" if controller.relays[relay].get_relay_state() else "off"
                            print(f"{relay} relay toggled {state}")
                    else:
                        print(f"Unknown command: {command}")
                else:
                    print(f"Unknown relay: {relay}")
            else:
                print("Invalid command format")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
