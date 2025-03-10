from typing import NamedTuple


class LocationMetadata(NamedTuple):
    City: str
    latitude: float
    longitude: float
    altitude: float
    TZ: float
