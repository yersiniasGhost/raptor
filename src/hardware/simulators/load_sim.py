from typing import List, Dict, Any

import pandas as pd

from hardware.hardware_base import HardwareBase
from utils import LogManager
from hardware.simulators.historical_data.load_singleton import LoadSingleton


class LoadSim(HardwareBase):

    def __init__(self, load_system:  dict):
        self.logger = LogManager().get_logger("PvPanelSimulator")
        load_csv = load_system.get("csv", "metered_load.csv")
        self.load_data = LoadSingleton(load_csv, 2025).load


    def get_identifier(self, devices: List[dict]) -> Dict[str, str]:
        return {d['mac']: f"NA-{d['mac']}" for d in devices}


    def data_acquisition(self, devices: List[Dict[str, Any]], scan_group: List[str]) -> Dict[str, Any]:
        now = pd.Timestamp.now()
        data = self.load_data.get_latest_date(now)
        output = {}
        for device in devices:
            mac = device['mac']
            output[mac] = {sc: data.get(sc, -1) for sc in scan_group}
        return output


    def get_points(self, names: List[str]) -> List:
            return []
