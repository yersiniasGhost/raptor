from typing import Tuple
import pandas as pd
from pathlib import Path
from utils import LogManager


class LoadData:
    def __init__(self, load_file: str, data_path: str, map_to_year: int = 2024):
        self.logger = LogManager().get_logger("LoadData")
        self.conversion = 1000.0
        file_path = Path(f'{data_path}/{load_file}')
        if file_path.exists():
            self.df = pd.read_csv(file_path)
            self.df.datetime = pd.to_datetime(self.df.datetime)
            self.df.set_index('datetime', inplace=True, drop=False)
        else:
            self.logger.error(f"No such input file for load: {file_path}")
            raise ValueError()

        self.df.index = self.df.index.map(lambda dt: dt.replace(year=map_to_year))
        self.df['datetime'] = self.df['datetime'].map(lambda dt: dt.replace(year=map_to_year))
        self.df.sort_index(inplace=True)
        self.df = self.df[~self.df.index.duplicated(keep='first')]


    def get_latest_index(self, now: pd.Timestamp) -> Tuple[pd.Timestamp, int]:
        date_idx = self.df.index[self.df.index <= pd.to_datetime(now)].max()
        row_index = self.df.index.get_loc(date_idx)
        return date_idx, row_index

    def get_latest_load_from_iloc(self, iloc_index: int) -> Tuple[pd.Timestamp, float]:
        data_row = self.df.iloc[iloc_index]
        consumption = data_row['Consumption'] * self.conversion
        return data_row['datetime'], consumption

    def get_latest_date(self, now: pd.Timestamp) -> pd.Series:
        return self.df.asof(now)

    def get_latest_demand(self, now: pd.Timestamp) -> float:
        row = self.get_latest_date(now)
        return row['Consumption']

