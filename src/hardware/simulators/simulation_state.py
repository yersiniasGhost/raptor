from collections import defaultdict
from typing import Dict, Any
from utils.singleton import Singleton


class SimulationState(metaclass=Singleton):

    def __init__(self):
        self.states: Dict[str, Any] = defaultdict(dict)

    def reset(self):
        self.states: Dict[str, Any] = defaultdict(dict)

    def add_state(self, system: str, hw_id: str, instance_data: dict):
        self.states[system][hw_id] = instance_data

    def get_state(self, system: str):
        return self.states.get(system, {})
