from typing import Tuple, Optional
import pandas as pd
from pathlib import Path
from .environment_conditions import EnvironmentConditions


def get_psm3_5min(lat: float,
                  long: float,
                  year: str,
                  api_key: str,
                  attributes: str = 'ghi,dhi,dni,wind_speed,air_temperature,solar_zenith_angle',
                  utc: str = 'false',
                  ) -> Tuple[pd.DataFrame, dict]:

    a = "dhi,dni,ghi,clearsky_dhi,clearsky_dni,clearsky_ghi,cloud_type,dew_point,air_temperature,surface_pressure,relative_humidity,solar_zenith_angle,total_precipitable_water,wind_direction,wind_speed,fill_flag"
    leap_year = 'false'
    name = 'John+Smith'
    reason = 'beta+testing'
    affiliation = 'my+institution'
    email = 'user2@company2.com'
    mailing_list = 'false'
    url = f"/api/nsrdb/v2/solar/psm3-5min-download.csv?api_key={api_key}&full_name={name}&email={email}&affiliation={affiliation}&reason=Needed&mailing_list=false&wkt=POINT({long}+{lat})&names={year}&attributes={a}&leap_day=false&utc=false&interval=5"
    url = f"https://developer.nrel.gov{url}"
    df = pd.read_csv(url)
    meta_data = df.iloc[:1]
    headers = df.iloc[1][:21]
    df = df.drop(df.index[:2])
    df = df.dropna(axis=1, how='all')
    df.columns = headers
    return df, meta_data


class IrradianceData:
    def __init__(self, lat: float, long: float, dl_year: int, map_to_year: int = 2025):
        self.api_key = '3iIo1di7wnXViLuf1WH85kEC8DtnAlwWVvwwX5kb'
        self.lat = lat
        self.long = long
        self.dl_year = dl_year
        self.map_to_year = map_to_year
        self.df: Optional[pd.DataFrame] = None
        self.metadata: Optional[dict] = None
        self._cache = {}
        self.last_ts = None
        self.last_data = None


    def load_irradiance_data(self, path: str):
        file_path = Path(f'{path}/psm3_data_{self.dl_year}_{self.lat}_{self.long}.csv')
        meta_file_path = Path(f'{path}/psm3_metadata_{self.dl_year}_{self.lat}_{self.long}.csv')
        if file_path.exists():
            self.df = pd.read_csv(file_path)
            metadata_df = pd.read_csv(meta_file_path)
            metadata_df['altitude'] = metadata_df['altitude'].astype(float)
            self.df.datetime = pd.to_datetime(self.df.datetime)
            self.df.set_index('datetime', inplace=True, drop=False)
        else:
            self.df, metadata_df = get_psm3_5min(self.lat, self.long, f"{self.dl_year}", self.api_key)
            self.df['datetime'] = pd.to_datetime(self.df[["Year", "Month", "Day", "Hour", "Minute"]])
            self.df.set_index('datetime', inplace=True, drop=False)
            self.df.index = pd.to_datetime(self.df.index)
            self.df.to_csv(file_path)
            meta_data_convert = {"City": "City", "Latitude": "latitude", "Longitude": "longitude",
                                 "Elevation": "altitude", "Time Zone": "TZ"}
            metadata_df = metadata_df.rename(columns=meta_data_convert)
            metadata_df = metadata_df[list(meta_data_convert.values())]
            metadata_df['altitude'] = metadata_df['altitude'].astype(float)
            metadata_df.to_csv(meta_file_path)

        self.df.index = self.df.index.map(lambda dt: dt.replace(year=self.map_to_year))
        self.df['datetime'] = self.df['datetime'].map(lambda dt: dt.replace(year=self.map_to_year))
        columns_to_convert = ['DNI', 'DHI', 'GHI', "Wind Speed", "Temperature"]
        self.df[columns_to_convert] = self.df[columns_to_convert].astype(float)
        self.df['Cloud Type'] = self.df['Cloud Type'].astype(int)
        self.metadata = {"City": metadata_df.iloc[0]['City'],
                         "latitude": metadata_df.iloc[0]['latitude'],
                         "longitude": metadata_df.iloc[0]['longitude'],
                         "altitude": metadata_df.iloc[0]['altitude'],
                         "TZ": metadata_df.iloc[0]['TZ']}


    def replay(self, start: pd.Timestamp, end: pd.Timestamp, delta_minutes=1):
        w = start
        last = None
        while w <= end:
            # row = self.get_latest_date(w)
            environment = self.get_latest_environment_data(w)
            dt = environment.datetime
            if dt != last:
                yield dt, environment
                last = dt
            w = w + pd.Timedelta(minutes=delta_minutes)

    def replay2(self, start: pd.Timestamp, end: pd.Timestamp, delta_minutes=1):
        w = start
        date, row_index = self.get_latest_index(w)
        environment = self.get_latest_environment_from_iloc(row_index)
        last = None
        while w <= end:
            dt = environment.datetime
            if dt != last:
                self.last_ts = dt
                yield dt, environment
                last = dt
            w = w + pd.Timedelta(minutes=delta_minutes)
            row_index += 1
            environment = self.get_latest_environment_from_iloc(row_index)
            while w < environment.datetime and row_index < len(self.df):
                w = w + pd.Timedelta(minutes=delta_minutes)
            while environment.datetime < w and row_index < len(self.df) - 1:
                row_index += 1
                environment = self.get_latest_environment_from_iloc(row_index)


    def get_latest_date(self, now: pd.Timestamp) -> pd.Series:
        if self.last_ts != now:
            self.last_ts = now
            self.last_data = self.df.asof(now)
        return self.last_data
        # try:
        #     return self.df.loc[now]
        # except KeyError:
        #     return self.df.asof(now)


    def get_latest_date3(self, now: pd.Timestamp) -> pd.Series:
        return self.df.asof(now)

    def get_latest_index(self, now: pd.Timestamp) -> Tuple[pd.Timestamp, int]:
        date_idx = self.df.index[self.df.index <= pd.to_datetime(now)].max()
        return date_idx, self.df.index.get_loc(date_idx)


    def get_latest_environment_from_iloc(self, iloc_index: int) -> EnvironmentConditions:
        solar_data_row = self.df.iloc[iloc_index]
        self.last_data = solar_data_row
        return self.get_environment(solar_data_row)

    def get_latest_environment_data(self, now: pd.Timestamp) -> EnvironmentConditions:
        solar_data_row = self.get_latest_date(now)
        return self.get_environment(solar_data_row)

    def get_environment(self, solar_data_row) -> EnvironmentConditions:
        environment = EnvironmentConditions(datetime=solar_data_row['datetime'],
                                            dni=solar_data_row['DNI'], dhi=solar_data_row['DHI'],
                                            ghi=solar_data_row['GHI'], temperature=solar_data_row["Temperature"],
                                            wind_speed=solar_data_row['Wind Speed'],
                                            cloud_type=int(solar_data_row["Cloud Type"]),
                                            City=self.metadata['City'],
                                            latitude=self.metadata['latitude'],
                                            longitude=self.metadata['longitude'],
                                            altitude=self.metadata['altitude'],
                                            TZ=int(self.metadata['TZ']))

        return environment
