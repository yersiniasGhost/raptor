from typing import Optional
import json
import logging
import sqlite3

from utils.envvars import EnvVars
from database.database_manager import DatabaseManager


def get_api_key(logger: logging.Logger = logging.getLogger(__name__)):
    db = DatabaseManager(EnvVars().db_path)
    try:
        with db.connection as conn:
            cursor = conn.execute("SELECT * FROM commission LIMIT 1")
            data = cursor.fetchone()
            if not data:
                logger.error("Unable to access commission database.")
                raise ValueError(f"Unable to access commission data.")
            return data["api_key"]
    except sqlite3.Error as e:
        logger.error(f"Failed to get commission data: {e}")
        return None


def get_mqtt_config(logger: logging.Logger = logging.getLogger(__name__)) -> Optional[dict]:
    db = DatabaseManager(EnvVars().db_path)
    try:
        with db.connection as conn:
            cursor = conn.execute("SELECT mqtt_config FROM commission LIMIT 1")
            data = cursor.fetchone()
            if not data:
                logger.error("Unable to access MQTT data from commission database.")
                raise ValueError("Unable to access MQTT data from commission database.")
            return json.loads(data['mqtt_config'])
    except sqlite3.Error as e:
        logger.error(f"Failed to get commission data: {e}")
        return None
