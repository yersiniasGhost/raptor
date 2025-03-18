from typing import List, Dict, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class HardwareBase(ABC):

    def __post_init__(self):
        pass

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
    def get_points(self, names: List[str]) -> List:
        pass

    @abstractmethod
    def get_identifier(self, devices: List[dict]) -> Dict[str, str]:
        pass
