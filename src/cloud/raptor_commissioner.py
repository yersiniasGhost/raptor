from typing import Optional
import requests
import logging
import sqlite3

from utils import EnvVars
from utils.mac_address import get_mac_address
from database.database_manager import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('raptor_commissioning')


class RaptorCommissioner:

    def __init__(self):
        self.api_base_url = EnvVars().api_url
        self.api_key: Optional[str] = None
        self.mac_address = get_mac_address()


    def commission(self):
        if self.api_key:
            logger.info("This VMC is already commissioned")
            return

        """Commission this Raptor with the server"""
        try:
            url = f"{self.api_base_url}/api/v2/raptor/commission"
            payload = {"mac_address": self.mac_address}

            logger.info(f"Attempting to commission Raptor with MAC: {self.mac_address}")
            response = requests.post(url, json=payload)

            if response.status_code == 200:
                data = response.json()
                self.api_key = data.get('api_key')
                envvars = EnvVars()
                raptor_id = data.get('raptor_id')
                api_key = data.get('api_key')
                firmware_tag = data.get('firmware_tag')
                db = DatabaseManager(envvars.db_path)
                with db.connection as conn:
                    conn.execute("""
                    REPLACE INTO commission (cloud_id, api_key, firmware_tag)
                        VALUES (?, ?, ?)
                    """, (raptor_id, api_key, firmware_tag))
                    conn.commit()
                logger.info("Successfully commissioned Raptor")
                return True
            else:
                logger.error(f"Commission failed: {response.text}")
                return False
        except sqlite3.Error as e:
            logger.error(f"Failed to update commission data: {e}")
            raise
        except Exception as e:
            logger.error(f"Commission error: {str(e)}")
            return False

