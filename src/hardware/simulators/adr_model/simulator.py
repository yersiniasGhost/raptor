from typing import NamedTuple, Tuple, Optional, List, Union, Dict
from dataclasses import dataclass, asdict
import pandas as pd
import numpy as np
import pytz
from datetime import datetime
from hardware.simulators.environment.environment_conditions import EnvironmentConditions
from .adr_model import ADRModel
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
    voltage: float
    current: float
    conditions: Dict[str, float]
    # solar_position: Dict[str, float]

    def asdict(self, measurements: List[str]) -> Dict[str, float]:
        valid = {"Current": self.current, "Voltage": self.voltage,
                 "Temperature": self.pv_temperature, "Power": self.power}
        output = {k: valid[k] for k in measurements if k in valid}
        return output


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
        poa_global = total_irradiance.iloc[0]['poa_global']
        pv_temperature = get_pv_temperature(total_irradiance.poa_global, conditions.temperature, conditions.wind_speed)
        eta, power = calculate_pvefficiency_adr(self.adr._asdict(), total_irradiance.poa_global,
                                                pv_temperature, self.panels.power_rating,
                                                self.panels.irradiance_normalized)
        power = power.iloc[0]
        pv_temperature = pv_temperature.iloc[0]
        module_v_mp = 120.0
        voltage, current = self.calculate_simple_iv(power, pv_temperature, module_v_mp)

        # prepare data so it can be stored in Mongo nicely
        # total_irradiance_dict = { key:  list(entry.values())[0] for key, entry in total_irradiance.to_dict().items() }
        conditions_dict = asdict(conditions)
        del conditions_dict['City']
        del conditions_dict['datetime']
        del conditions_dict['latitude']
        del conditions_dict['longitude']
        return InstantData(eta=eta.iloc[0],
                           power=power,
                           irradiance=poa_global,
                           temperature=conditions.temperature,
                           pv_temperature=pv_temperature,
                           conditions=conditions_dict,
                           voltage=voltage,
                           current=current
                           # solar_position=solar_position.iloc[0].to_dict()
                )


    @staticmethod
    def calculate_simple_iv(pv_power: float, pv_temp: float,
                            v_mp_ref: float,  # Module rated voltage at STC (V)
                            modules_per_string: int = 1,  # Number of modules in series
                            strings_per_inverter: int = 1,  # Number of parallel strings
                            beta_voc: float = -0.0037,  # Temperature coefficient of voltage (%/°C)
                            temp_ref: float = 25.0,  # Reference temperature (°C)
                            ) -> Tuple[float, float]:
        # Adjust voltage based on temperature coefficient
        temp_diff = pv_temp - temp_ref
        v_mp_temp_adjusted = v_mp_ref * (1 + beta_voc * temp_diff / 100)

        # Calculate system voltage (modules in series)
        v_system = v_mp_temp_adjusted * modules_per_string
        # The current scales with irradiance approximately linearly
        i_module = pv_power / (v_system * strings_per_inverter)

        # Calculate system current (strings in parallel)
        i_system = i_module * strings_per_inverter
        return v_system, i_system
