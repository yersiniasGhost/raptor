from typing import Optional
from dotenv import load_dotenv
from pathlib import Path
import os
import sys

from .singleton import Singleton


class EnvVars(metaclass=Singleton):

    def __init__(self):
        # Load .env file if it exists
        env_path = Path.home() / ".env"
        if not env_path.exists():
            print(f"Error: .env file not found at {env_path}")
            sys.exit(1)

        load_dotenv(env_path)
        self.env_variables = {}
        # Database settings
        self.db_path = self._get_required('DB_PATH')
        self.log_path = self.get_env("LOG_PATH", "/var/log/raptor")

        # API settings
        # self.phone_home_url = self._get_required('VMC_HOME_URL')
        self.api_url = self._get_required('API_URL')

        # Repository settings
        self.repository_path = self.get_env("VMC_REPOSITORY_PATH", "/root/raptor")
        self.schema_path = self.get_env("SCHEMA_PATH", "/root/raptor/src/database/schema.sql")

        # Application settings
        self.debug = self.get_bool('DEBUG', "False")
        self.log_level = self.get_env('LOG_LEVEL', 'INFO')
        self.enable_simulators = self.get_bool("RAPTOR_SIMULATOR", "False")
        


    def get_env(self, variable: str, default: Optional[str] = None) -> Optional[str]:
        return self.env_variables.get(variable) or self.env_variables.setdefault(
            variable,
            os.getenv(variable, default)
        )


    def _get_required(self, key: str) -> str:
        value = self.get_env(key)
        if value is None:
            raise ValueError(f"Missing required environment variable: {key}")
        return value

    def get_bool(self, key: str, default: str) -> bool:
        value = self.get_env(key, default)
        return value.lower() in ('true', '1', 'yes', 'y')

