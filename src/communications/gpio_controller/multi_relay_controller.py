from typing import Dict
from gpio_controller import GPIOController


class MultiRelayError(Exception):
    """Base class for actuator control exceptions"""
    pass


class MultiRelayController:
    def __init__(self, config: Dict[str, int], fpga_gpio_label="50004010.fpga_gpio"):
        self.label = fpga_gpio_label
        self.relays: Dict[str, GPIOController] = {name: GPIOController(chip_label=self.label, line_number=line) for name, line in config.items()}
        self.verify_gpio()


    def set_relay(self, name: str, state: bool) -> bool:
        relay = self.relays.get(name)
        if not relay:
            raise MultiRelayError(f"No relay named: {name} is configured.")
        success = relay.set_relay(state)
        return success

    def verify_gpio(self):
        list(self.relays.values())[0].verify_gpio()

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

    def cleanup(self, polarity: str):
        """Turn off all relays"""
        state = False if polarity == "high" else True
        self.set_all(state)
