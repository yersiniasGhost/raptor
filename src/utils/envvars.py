from typing import Optional
from dotenv import load_dotenv
from pathlib import Path
import os
import sys

from .singleton import Singleton


class EnvVars(metaclass=Singleton):

    def __init__(self):
        # Load .env file if it exists
        env_path = Path("~/.env")
        if not env_path.exists():
            print(f"Error: .env file not found at {env_path}")
            sys.exit(1)

        load_dotenv(env_path)
        self.env_variables = {}
        # Database settings
        self.db_path = self._get_required('DB_PATH')
        self.tsdb_path = self._get_required("TSDB_PATH")

        # API settings
        self.phone_home_url = self._get_required('VMC_HOME_URL')
        self.api_url = self._get_required('API_URL')

        # Repository settings
        self.repository_path = self._getenv("VMC_REPOSITORY_PATH", "/root/raptor")

        # Application settings
        self.debug = self._get_bool('DEBUG', False)
        self.log_level = self._getenv('LOG_LEVEL', 'INFO')


    def _getenv(self, variable: str, default: Optional[str] = None) -> Optional[str]:
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

