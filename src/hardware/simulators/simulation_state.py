from collections import defaultdict
from typing import Dict, Any, Optional
from utils.singleton import Singleton

REMAINING_CAPACITY = "Remaining_Capacity"
STATE_OF_CHARGE = "State_of_Charge"
CURRENT = "Current"
VOLTAGE = "Pack_Voltage"


class SimulationState(metaclass=Singleton):

    def __init__(self):
        self.states: Dict[str, Any] = defaultdict(dict)
        self.previous_states: Optional[Dict[str, Any]] = None

    def reset(self):
        self.previous_states = self.states
        self.states: Dict[str, Any] = defaultdict(dict)

    def add_state(self, system: str, hw_id: str, instance_data: dict):
        self.states[system][hw_id] = instance_data

    def get_state(self, system: str):
        return self.states.get(system, {})

    def get_previous(self, system: str, hardware_id: str):
        prev = self.previous_states.get(system)
        if not prev:
            if system == "BMS":
                return {REMAINING_CAPACITY: 50.0}
        return prev[hardware_id]
