from dotenv import load_dotenv
import os
from .singleton import Singleton
from typing import Optional


class EnvVars(metaclass=Singleton):

    def __init__(self):
        # Load .env file if it exists
        load_dotenv()
        self.env_variables = {}
        # Database settings
        self.db_path = self._get_required('DB_PATH')
        self.tsdb_path = self._get_required("TSDB_PATH")

        # API settings
        self.phone_home_url = self._get_required('VMC_HOME_URL')
        self.api_url = self._get_required('API_URL')

        # Application settings
        self.debug = self._get_bool('DEBUG', False)
        self.log_level = self._getenv('LOG_LEVEL', 'INFO')


    def _getenv(self, variable: str, default: Optional[str] = None) -> Optional[str]:
        # Use dict.get() directly with default value instead of checking None separately
        return self.env_variables.get(variable) or self.env_variables.setdefault(
            variable,
            os.getenv(variable, default)
        )

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    def _get_required(self, key: str) -> str:
        value = self._getenv(key)
        if value is None:
            raise ValueError(f"Missing required environment variable: {key}")
        return value

    @staticmethod
    def _get_bool(self, key: str, default: bool) -> bool:
        value = self._getenv(key, default)
        return value.lower() in ('true', '1', 'yes', 'y')

