from typing import NamedTuple, List, Dict, Any
import pandas as pd
from hardware.hardware_base import HardwareBase
from .historical_data.irradiance_data import IrradianceData
from .historical_data.irradiance_singleton import IrradianceSingleton
from .adr_model import PanelConfig, ADRSimulator, ADRModel, InstantData, get_location_from_meta_data
from utils.logger import LogManager


class PanelDeployment(NamedTuple):
    latitude: float
    longitude: float
    power_rating: float = 1000.0
    irradiance_normalized: float = 1000.0


class PanelModel(NamedTuple):
    id: str
    tilt_angle: float
    azimuth: float
    capacity: float
    model_type: str
    model_parameters: dict


class PvPanelSimulator(HardwareBase):

    def __init__(self, panel_config: dict):
        self.logger = LogManager().get_logger("PvPanelSimulator")
        self.panel_config: PanelDeployment = PanelDeployment(**panel_config)
        irradiance = IrradianceSingleton(self.panel_config.latitude,
                                         self.panel_config.longitude,
                                         2020, 2025)
        self.irradiance: IrradianceData = irradiance.irradiance


    def get_identifier(self, devices: List[dict]) -> Dict[str, str]:
        return {d['mac']: f"NA-{d['mac']}" for d in devices}

    def data_acquisition(self, panel_strings: List[Dict[str, Any]], scan_group: List[str]) -> Dict[str, Any]:
        """
        The panels is a list of dicts:  ID to PanelModel data.
        """
        now = pd.Timestamp.now()
        # Calculate the generation of power based upon the ADR model and Irradiance data
        output = {}
        irradiance_data = self.irradiance.get_latest_environment_data(now)
        for panel_string in panel_strings:
            tilt = panel_string['tilt']
            orientation = panel_string['orientation']
            panel_config = PanelConfig(tilt_angle=tilt, azimuth=orientation,
                                       latitude=self.panel_config.latitude, longitude=self.panel_config.longitude,
                                       power_rating=self.panel_config.power_rating)
            loc_data = {"City": irradiance_data.City, "latitude": irradiance_data.latitude,
                        "longitude": irradiance_data.longitude,
                        "TZ": irradiance_data.TZ, "altitude": irradiance_data.altitude}
            loc = get_location_from_meta_data(loc_data)
            model_parameters = panel_string['model_parameters']
            adr = ADRModel(**model_parameters)
            sim = ADRSimulator(panels=panel_config, adr=adr, loc=loc)
            result: InstantData = sim.calculate_one(now, irradiance_data)
            panel_id = panel_string['mac']
            output[panel_id] = result.asdict(scan_group)
        return output

    def get_points(self, names: List[str]) -> List:
        return []
