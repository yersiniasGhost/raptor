from typing import List, Dict, Any
import random
from hardware.hardware_base import HardwareBase


import logging

logger = logging.getLogger(__name__)


class MockHardware(HardwareBase):

    def data_acquisition(self, devices: List[Dict[str, Any]], scan_group: List[str]) -> Dict[str, Any]:
        output = {}
        for device in devices:
            slave_id = device['mac']
            output[slave_id] = {r.replace(' ', '_'): random.random() for r in scan_group}

        return output

    def get_points(self, names: List[str]) -> List:
        return []