import sys
import signal
from banner_alarm import BannerAlarm


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
        # BANNER Alarm configuration:
        config = { "relays": {"blue": 1, "green": 2, "red": 4, "alarm": 3},
                   "polarity": "high"}
        controller = BannerAlarm(configuration=config)

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
            if parts[0] == "quit":
                controller.cleanup()
                break
            if parts[0] == "on1":
                controller.activate_alarm("default")
            if parts[0] == "on2":
                controller.activate_alarm("flash_all")
            if parts[0] == "on3":
                controller.activate_alarm("alternate")
            elif parts[0] == "off":
                controller.deactivate_alarm()
            else:
                print(f"Unknown command")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
