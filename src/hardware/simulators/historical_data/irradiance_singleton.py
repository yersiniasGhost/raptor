from utils.singleton import Singleton
from .irradiance_data import IrradianceData


class IrradianceSingleton(metaclass=Singleton):
    """
    When running in a simulator mode, we should instantiate the Irradiance data one time
    rather than multiple loads.  This singleton will wrap the irradiance data.
    """
    def __init__(self, lat: float, long: float, dl_year: int, map_to_year: int = 2025):

        self.irradiance = IrradianceData(lat, long, dl_year, map_to_year)
        local_path = "/home/frich/devel/valexy/raptor/data/weather"
        self.irradiance.load_irradiance_data(local_path)
