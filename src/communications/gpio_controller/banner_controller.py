from .gpio_controller import GPIOController


class MultiRelayController:
    def __init__(self):
        # Initialize multiple GPIO controllers
        self.relays = {
            "red": GPIOController(chip_label="50004010.fpga_gpio", line_number=1),
            "green": GPIOController(chip_label="50004010.fpga_gpio", line_number=2),
            "blue": GPIOController(chip_label="50004010.fpga_gpio", line_number=3),
            "audible": GPIOController(chip_label="50004010.fpga_gpio", line_number=4),
        }

    def set_all(self, state):
        """Set all relays to the same state"""
        success = True
        for relay in self.relays.values():
            if not relay.set_relay(state):
                success = False
        return success

    def get_status_all(self):
        """Get status of all relays"""
        return {name: relay.get_relay_state() for name, relay in self.relays.items()}

    def cleanup(self):
        """Turn off all relays"""
        self.set_all(False)
