from typing import Union, List, Dict, Tuple

import numpy as np
import pandas as pd
import pvlib
from pvlib import location
from pvlib.irradiance import get_total_irradiance
from pvlib.pvarray import pvefficiency_adr

'''
# Example location data:
{'USAF': 723170,
 'Name': '"GREENSBORO PIEDMONT TRIAD INT"',
 'State': 'NC',
 'TZ': -5.0,
 'latitude': 36.1,
 'longitude': -79.95,
 'altitude': 273.0}
'''


def get_location(latitude: float, longitude: float, tz: float, altitude: float, name: str) -> location.Location:
    return location.Location(latitude, longitude, tz=tz, altitude=altitude, name=name)


def get_location_from_meta_data(metadata: dict) -> location.Location:
    return location.Location.from_tmy(metadata)


def get_solar_position(loc: location.Location, times: pd.DatetimeIndex) -> pd.DataFrame:
    times = times - pd.Timedelta(hours = loc.tz)
    return loc.get_solarposition(times)


'''
   surface_tilt : numeric
        Panel tilt from horizontal. [degree]
    surface_azimuth : numeric
        Panel azimuth from north. [degree]
    solar_zenith : numeric
        Solar zenith angle. [degree]
    solar_azimuth : numeric
        Solar azimuth angle. [degree]
'''


def get_total_poa_irradiance(surface_tilt: float, surface_azimuth: float,
                             solar_zenith: Union[pd.Series, float], solar_azimuth: Union[pd.Series, float],
                             dni: pd.Series, ghi: Union[pd.Series, float], dhi: Union[pd.Series, float]) -> pd.DataFrame:
    # x = get_total_irradiance(surface_tilt, surface_azimuth, solar_zenith, solar_azimuth, dni, ghi, dhi)
    # print(surface_tilt, surface_azimuth, solar_zenith.iloc[0], solar_azimuth.iloc[0], dni, ghi, dhi)
    # print(x.iloc[0])
    # print('--------------------------')
    return get_total_irradiance(surface_tilt, surface_azimuth, solar_zenith, solar_azimuth, dni, ghi, dhi)


def get_pv_temperature(poa_global: Union[pd.Series, float], air_temp: Union[pd.Series, float],
                       wind_speed: Union[pd.Series, float]) -> Union[pd.Series, float]:
    return pvlib.temperature.faiman(poa_global, air_temp, wind_speed)

'''
ADR model parameters.  These have been determined by fitting STC data in a laboratory.
Example ADR parameters
adr_params = {'k_a': 0.99924,
              'k_d': -5.49097,
              'tc_d': 0.01918,
              'k_rs': 0.06999,
              'k_rsh': 0.26144
              }
'''


def calculate_pvefficiency_adr(adr_params: Dict[str, float],
                               poa_global: Union[float, List[float], pd.Series],
                               temp_pv: Union[float, List[float], pd.Series],
                               array_size: float,                             # W
                               irradiance_normalization: float = 1000.0,      # W/m2
                               ) -> Tuple[np.array, np.array]:

    eta_rel = pvefficiency_adr(poa_global, temp_pv, **adr_params)
    pv_power = array_size * eta_rel * (poa_global / irradiance_normalization)

    return eta_rel, pv_power
