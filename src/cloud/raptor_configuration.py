from typing import Optional
import json
import requests
from utils import EnvVars, get_mac_address, get_api_key
from utils import LogManager

logger = LogManager().get_logger(__name__)


class RaptorConfiguration:

    def __init__(self):
        self.api_base_url = EnvVars().api_url
        self.api_key: Optional[str] = get_api_key()
        self.mac_address = get_mac_address()


    def get_configuration(self):
        """Get configuration using the API key from commissioning"""
        if not self.api_key:
            logger.error("No API key available. Run commission() first.")
            return None

        try:
            url = f"{self.api_base_url}/api/v2/raptor/configuration"
            headers = {'X-API-Key': self.api_key}
            params = {'mac_address': self.mac_address}

            logger.info("Fetching configuration")
            response = requests.get(url, headers=headers, params=params)

            if response.status_code == 200:
                config = response.json()
                logger.info("Successfully retrieved configuration")
                self.save_configuration(config)
                return config
            else:
                logger.error(f"Configuration fetch failed: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Configuration error: {str(e)}")
            return None


    @staticmethod
    def save_configuration(config, filename='raptor_config.json'):
        """Save configuration to a file"""
        try:
            with open(filename, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Configuration saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {str(e)}")
            return False
