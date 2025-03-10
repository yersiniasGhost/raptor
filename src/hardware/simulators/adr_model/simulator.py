from typing import NamedTuple, Tuple, Optional, Iterable, Union, Dict
from dataclasses import dataclass, asdict
import pandas as pd
import pytz
from datetime import datetime
from environment.environment_conditions import EnvironmentConditions
from . import ADRModel
from .adr_module_efficiency import get_solar_position, get_location_from_meta_data
from .adr_module_efficiency import get_total_poa_irradiance, calculate_pvefficiency_adr, get_pv_temperature
from pvlib import location


class PanelConfig(NamedTuple):
    tilt_angle: float  #  The tilt angle refers to the angle the PV panels set are relative to the horizontal ground.
    azimuth: float     #  The azimuth angle is the compass direction that the PV panels face. It is measured in degrees from true north.
    latitude: float
    longitude: float
    power_rating: float = 1000.0
    irradiance_normalized: float = 1000.0


class InstantData(NamedTuple):
    eta: float
    power: float
    irradiance: Dict[str, float]
    temperature: float
    pv_temperature: float
    conditions: Dict[str, float]
    # solar_position: Dict[str, float]



@dataclass
class ADRSimulator:
    panels: PanelConfig
    adr: ADRModel
    loc: Optional[location.Location] = None
    metadata: Optional[dict] = None
    data: Optional[pd.DataFrame] = None

    def set_system(self, other: "ADRSimulator"):
        self.loc = other.loc
        self.metadata = other.metadata
        self.data = other.data

    # api_key = '3iIo1di7wnXViLuf1WH85kEC8DtnAlwWVvwwX5kb'
    def prepare_psm3_history(self, year: int, api_key: str, shift_tz: bool = False):
        metadata, data = get_yearly_psm3_data(self.panels.latitude, self.panels.longitude, year, api_key)
        self.loc = get_location_from_meta_data(metadata)
        self.metadata = metadata
        self.data = data
        if shift_tz:
            self.data.index = self.data.index.tz_localize('UTC').tz_convert(pytz.FixedOffset(self.loc.tz * 60))



    def calculate(self) -> pd.DataFrame:
        solar_position = get_solar_position(self.loc, self.data.index)
        total_irradiance = get_total_poa_irradiance(self.panels.tilt_angle, self.panels.azimuth,
                                                    solar_position.apparent_zenith, solar_position.azimuth,
                                                    self.data.DNI, self.data.GHI, self.data.DHI)
        pv_temperature = get_pv_temperature(total_irradiance.poa_global, self.data.Temperature, self.data['Wind Speed'])
        eta, power = calculate_pvefficiency_adr(self.adr._asdict(), total_irradiance.poa_global,
                                                pv_temperature, self.panels.power_rating,
                                                self.panels.irradiance_normalized)
        return pd.DataFrame({'eta': eta, 'power': power, 'poa_global': total_irradiance.poa_global})


    def calculate_one(self, in_datetime: Union[str, datetime], conditions: EnvironmentConditions) -> InstantData:
        single_date_time_index = (pd.DatetimeIndex([pd.to_datetime(in_datetime)]) if isinstance(in_datetime, str)
                                  else pd.DatetimeIndex([pd.to_datetime(in_datetime)]))
        solar_position = get_solar_position(self.loc, single_date_time_index)
        total_irradiance = get_total_poa_irradiance(self.panels.tilt_angle, self.panels.azimuth,
                                                    solar_position.apparent_zenith, solar_position.azimuth,
                                                    conditions.dni, conditions.ghi, conditions.dhi)
        pv_temperature = get_pv_temperature(total_irradiance.poa_global, conditions.temperature, conditions.wind_speed)
        eta, power = calculate_pvefficiency_adr(self.adr._asdict(), total_irradiance.poa_global,
                                                pv_temperature, self.panels.power_rating,
                                                self.panels.irradiance_normalized)

        # prepare data so it can be stored in Mongo nicely
        # total_irradiance_dict = { key:  list(entry.values())[0] for key, entry in total_irradiance.to_dict().items() }
        poa_global = total_irradiance.iloc[0]['poa_global']
        conditions_dict = asdict(conditions)
        del conditions_dict['City']
        del conditions_dict['datetime']
        del conditions_dict['latitude']
        del conditions_dict['longitude']
        return InstantData(eta=eta.iloc[0],
                           power=power.iloc[0],
                           irradiance=poa_global,
                           temperature=conditions.temperature,
                           pv_temperature=pv_temperature.iloc[0],
                           conditions=conditions_dict,
                           # solar_position=solar_position.iloc[0].to_dict()
                )
