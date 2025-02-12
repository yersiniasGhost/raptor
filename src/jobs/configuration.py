from typing import Optional
import os
import sys
import json
import requests
import logging
from uuid import getnode as get_mac

from utils.mac_address import get_mac_address

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('raptor_commissioning')


class RaptorCommissioner:

    def __init__(self, api_base_url):
        self.api_base_url = api_base_url
        self.api_key: Optional[str] = None
        self.mac_address = get_mac_address()


    def commission(self):
        """Commission this Raptor with the server"""
        try:
            url = f"{self.api_base_url}/api/v2/raptor/commission"
            payload = {
                "mac_address": self.mac_address
            }

            logger.info(f"Attempting to commission Raptor with MAC: {self.mac_address}")
            response = requests.post(url, json=payload)

            if response.status_code == 200:
                data = response.json()
                self.api_key = data.get('api_key')
                logger.info("Successfully commissioned Raptor")
                return True
            else:
                logger.error(f"Commission failed: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Commission error: {str(e)}")
            return False



    def get_configuration(self):
        """Get configuration using the API key from commissioning"""
        if not self.api_key:
            logger.error("No API key available. Run commission() first.")
            return None

        try:
            url = f"{self.api_base_url}/api/v2/raptor/configuration"
            headers = {
                'X-API-Key': self.api_key
            }
            params = {
                'mac_address': self.mac_address
            }

            logger.info("Fetching configuration")
            response = requests.get(url, headers=headers, params=params)

            if response.status_code == 200:
                config = response.json()
                logger.info("Successfully retrieved configuration")
                return config
            else:
                logger.error(f"Configuration fetch failed: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Configuration error: {str(e)}")
            return None



    def save_configuration(self, config, filename='raptor_config.json'):
        """Save configuration to a file"""
        try:
            with open(filename, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Configuration saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {str(e)}")
            return False


def main():
    # API base URL - update this for your environment
    API_BASE_URL = os.getenv('CREM3_API_URL', 'http://192.168.1.25:3000')

    # Create commissioner instance
    commissioner = RaptorCommissioner(API_BASE_URL)

    # Attempt commissioning
    if not commissioner.commission():
        logger.error("Failed to commission Raptor")
        sys.exit(1)

    # Get configuration
    config = commissioner.get_configuration()
    if not config:
        logger.error("Failed to get configuration")
        sys.exit(1)

    # Save configuration
    if not commissioner.save_configuration(config):
        logger.error("Failed to save configuration")
        sys.exit(1)

    logger.info("Raptor successfully commissioned and configured")


if __name__ == "__main__":
    main()