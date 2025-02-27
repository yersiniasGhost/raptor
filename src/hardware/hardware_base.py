from typing import List, Dict, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class HardwareBase(ABC):

    def __post_init__(self):
        pass

    @abstractmethod
    def data_acquisition(self, devices: List[Dict[str, Any]], scan_group: List[str]):
        raise ValueError("Must be implemented in sub-class")

    @abstractmethod
    def get_points(self, names: List[str]) -> List:
        pass
