from typing import List, Dict, Any, Tuple, Union, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod
from utils import LogManager
import json
import os


@dataclass
class HardwareBase(ABC):
    hardware_id: Optional[int] = None                    # Database hardware ID for state tracking
    states_config_path: Optional[str] = None             # Path to states configuration JSON file
    _states_config: Optional[Dict[str, Any]] = None      # Cached states configuration

    def __post_init__(self):
        self.logger = LogManager().get_logger("HardwareBase")

    def load_states_config(self) -> Optional[Dict[str, Any]]:
        """Load states configuration from JSON file on demand"""
        if self._states_config is not None:
            return self._states_config

        if not self.states_config_path or not os.path.exists(self.states_config_path):
            self.logger.warning(f"States configuration file not found: {self.states_config_path}")
            return None

        try:
            with open(self.states_config_path, 'r') as f:
                self._states_config = json.load(f)
            self.logger.info(f"Loaded states configuration from {self.states_config_path}")
            return self._states_config
        except Exception as e:
            self.logger.error(f"Failed to load states configuration: {e}")
            return None

    @abstractmethod
    def data_acquisition(self, devices: List[Dict[str, Any]], scan_group: List[str], hardware_id: str) -> Dict[str, Any]:
        """
        :param devices: A list of devices which is defined by a Dict of ID to device parameters
        :param scan_group: A list of named points or registers to be read and recorded
        :param hardware_id
        :return: Dict of device ID to dict of { point: value }
        """
        raise ValueError("Must be implemented in sub-class")

    @abstractmethod
    def get_points(self, names: List[str]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_identifier(self, devices: List[dict]) -> Dict[str, str]:
        pass

    def ping_hardware(self) -> Tuple[str, Union[str, bool]]:
        return "Ping TBD", True

    def reset_hardware(self) -> Tuple[str, Union[str, bool]]:
        return "Reset Hardware TBD", True

    def scenario_status(self, mode: str, devices: List[dict], hardware_id: str) -> dict:
        return {}

    # For inverter hardware
    def has_input_AC(self, devices: List[dict]) -> bool:
        pass

    # State management methods - to be implemented by subclasses
    @abstractmethod
    def set_operational_state(self, state_name: str) -> Dict[str, Any]:
        """
        Set the operational state of the hardware
        :param state_name: Name of the state to set (e.g., "Battery Priority", "AC Only")
        :return: Dict with success status and any error information
        """
        raise ValueError("Must be implemented in sub-class")

    @abstractmethod
    def get_current_state(self) -> str:
        """
        Get the current operational state of the hardware
        :return: Current state name or None if no state set
        """
        raise ValueError("Must be implemented in sub-class")

    @abstractmethod
    def validate_state_change(self, state_name: str) -> Dict[str, Any]:
        """
        Validate if a state change is possible given current conditions
        :param state_name: Name of the state to validate
        :return: Dict with validation result and any error information
        """
        raise ValueError("Must be implemented in sub-class")

    @abstractmethod
    def get_available_states(self) -> List[str]:
        """
        Get list of available operational states for this hardware
        :return: List of state names
        """
        raise ValueError("Must be implemented in sub-class")
