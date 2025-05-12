from typing import Optional
import requests
import sqlite3

from utils import EnvVars
from utils.mac_address import get_mac_address
from database.database_manager import DatabaseManager

# Configure logging
from utils import LogManager


class RaptorCommissioner:

    def __init__(self):
        self.logger = LogManager().get_logger("RaptorCommissioner")
        self.api_base_url = EnvVars().api_url
        self.api_key: Optional[str] = None
        self.mac_address = get_mac_address()


    def commission(self):
        if self.api_key:
            self.logger.info("This VMC is already commissioned")
            return

        """Commission this Raptor with the server"""
        try:
            url = f"{self.api_base_url}/api/v2/raptor/commission"
            payload = {"mac_address": self.mac_address}

            self.logger.info(f"Attempting to commission Raptor with MAC: {self.mac_address}")
            self.logger.info(f"Using: {url} and payload: {payload}")
            response = requests.post(url, json=payload)

            if response.status_code == 200:
                self.logger.info("Successfully got response.")
                data = response.json()
                self.api_key = data.get('api_key')
                envvars = EnvVars()
                raptor_id = data.get('raptor_id')
                firmware_tag = data.get('firmware_tag')
                db = DatabaseManager(envvars.db_path)

                try:
                    with db.connection as conn:
                        conn.execute("""
                        UPDATE commission 
                        SET api_key = ?, firmware_tag = ?
                        WHERE raptor_id = ?
                        """, (self.api_key, firmware_tag, raptor_id))

                        # If no rows were updated, insert a new row
                        if conn.total_changes == 0:
                            conn.execute("""
                            INSERT INTO commission (raptor_id, api_key, firmware_tag)
                            VALUES (?, ?, ?)
                            """, (raptor_id, self.api_key, firmware_tag))
                except sqlite3.Error as e:
                    self.logger.error(f"Database error: {e}")

                # with db.connection as conn:
                #     conn.execute("""
                #     REPLACE INTO commission (raptor_id, api_key, firmware_tag)
                #         VALUES (?, ?, ?)
                #     """, (raptor_id, self.api_key, firmware_tag))
                #     conn.commit()
                self.logger.info("Successfully commissioned Raptor", self.api_key, firmware_tag)
                return True
            else:
                self.logger.error(f"Commission failed: {response.text}")
                return False
        except sqlite3.Error as e:
            self.logger.error(f"Failed to update commission data: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Commission error: {str(e)}")
            return False

