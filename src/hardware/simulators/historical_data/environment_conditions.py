from typing import Optional
from dataclasses import dataclass
import pandas as pd


@dataclass
class EnvironmentConditions:
    datetime: pd.Timestamp
    dni: float
    dhi: float
    ghi: float
    temperature: float
    wind_speed: float
    cloud_type: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude:  Optional[float] = None
    TZ:  Optional[float] = None
    City: str = "None"
