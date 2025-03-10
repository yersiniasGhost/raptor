from typing import List, Dict, Any
import pandas as pd
from hardware.hardware_base import HardwareBase
from .historical_data import IrradianceData, EnvironmentConditions
from utils.logger import LogManager


class WeatherStationSim(HardwareBase):

    def __init__(self, ws_config: dict):
        self.logger = LogManager().get_logger("WeatherStationSim")
        self.irradiance = IrradianceData(ws_config["latitude"], ws_config["longitude"],
                                         ws_config['dl_year'], ws_config['map_to_year'])

    def data_acquisition(self, ws: List[Dict[str, Any]], scan_group: List[str]) -> Dict[str, Any]:
        """
        The panels is a list of dicts:  ID to PanelModel data.
        """
        now = pd.Timestamp.now()
        # Calculate the generation of power based upon the ADR model and Irradiance data
        output = {}
        irradiance_data: EnvironmentConditions = self.irradiance.get_latest_environment_data(now)
        for ws_data in ws:
            ws_id = ws_data['id']
            data = {}
            for measurement in scan_group:
                if hasattr(irradiance_data, measurement):
                    data[measurement] = getattr(irradiance_data, measurement)
            output[ws_id] = data
        return output


    def get_points(self, names: List[str]) -> List:
        return []
