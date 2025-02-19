from typing import List, Dict, Any
from abc import ABC, abstractmethod


class HardwareBase(ABC):

    @abstractmethod
    def data_acquisition(self, devices: List[Dict[str, Any]], scan_group: List[str]):
        raise ValueError("Must be implemented in sub-class")