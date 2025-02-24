from typing import Optional, Dict, Any
import json
import jsonschema
import requests
from utils import EnvVars, get_mac_address
from utils import LogManager
from database.db_utils import get_api_key
from database.database_manager import DatabaseManager

logger = LogManager().get_logger(__name__)


class RaptorConfiguration:
    SCHEMA = {
        "type": "object",
        "required": ["mqtt", "telemetry", "hardware"],
        "properties": {
            "mqtt": {
                "type": "object",
                "required": ["broker", "port", "username", "password", "client_id"],
                "properties": {
                    "broker": {"type": "string"},
                    "port": {"type": "integer"},
                    "username": {"type": "string"},
                    "password": {"type": "string"},
                    "client_id": {"type": "string"}
                }
            },
            "telemetry": {
                "type": "object",
                "required": ["interval", "topics"],
                "properties": {
                    "interval": {"type": "integer"},
                    "telemetry_path": {"type": "string"},
                    "messages_path": {"type": "object"},
                    "alarms_path": {"type": "object"},
                    "status_path": {"type": "object"}
                }
            },
            "hardware": {"type": "object"}
        }
    }

    def __init__(self):
        self.api_base_url = EnvVars().api_url
        self.api_key: Optional[str] = get_api_key(logger)
        self.mac_address = get_mac_address()


    @staticmethod
    def validate_json(data: Dict[str, Any]) -> bool:
        try:
            jsonschema.validate(instance=data, schema=RaptorConfiguration.SCHEMA)
            return True
        except jsonschema.exceptions.ValidationError as e:
            logger.error(f"Configuration data validation error: {e}")
            logger.error(f"EXPECTED: {RaptorConfiguration.SCHEMA}")
            logger.error(f"GOT:      {data}")
            return False


    def get_configuration(self):
        """Get configuration using the API key from commissioning"""
        if not self.api_key:
            logger.error("No API key available. Run commission() first.")
            raise ValueError("No APIO key available.  Run commission() first?")

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
                raise ValueError(f"Response code from CREM3 configuration API: {response.status_code}")

        except Exception as e:
            logger.error(f"Configuration error: {e}")
            raise


    def save_configuration(self, config_data: Dict[str, Any], filename: Optional[str] = None):
        """ Clear the existing configuration data.  Keep the telemetry data in case of roll back? """

        """Save configuration to the SQLite database"""

        # Validate
        if not self.validate_json(config_data):
            logger.error("Did not validate the configuration data.")
            raise ValueError(f"Invalid Raptor Configuration")
        try:
            # Extract MQTT and telemetry config
            mqtt_config = json.dumps(config_data["mqtt"])
            telemetry_config = json.dumps(config_data["telemetry"])
            db = DatabaseManager(EnvVars().db_path)
            db.clear_existing_configuration()
            db.update_telemetry(telemetry_config, mqtt_config)
            db.add_hardware(config_data['hardware'])
        except Exception as e:
            logger.error(f"Unable to save configuration: {config_data}")
            logger.error(f"Error: {e}")
            raise

        if filename:
            """Save configuration to a file"""
            try:
                with open(filename, 'w') as f:
                    json.dump(config_data, f, indent=2)
                logger.info(f"Configuration saved to {filename}")
                return True
            except Exception as e:
                logger.error(f"Failed to save configuration: {str(e)}")
                raise
