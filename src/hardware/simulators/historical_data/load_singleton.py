from utils.singleton import Singleton
from .load_data import LoadData


class LoadSingleton(metaclass=Singleton):
    """
    When running in a simulator mode, we should instantiate the Load data one time
    rather than multiple loads.
    """
    def __init__(self, csv_file: str, map_to_year: int = 2025):

        local_path = "/home/frich/devel/valexy/raptor/data/loads"
        self.load = LoadData(csv_file, local_path, map_to_year)

