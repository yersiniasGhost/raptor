from typing import Optional
import json
from logging import Logger
import sqlite3

from utils.envvars import EnvVars
from database.database_manager import DatabaseManager
from cloud.mqtt_config import MQTTConfig


def get_api_key(logger: Logger):
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

# def get_hardware_configuration(logger: Logger) -> dict:
#     db = DatabaseManager(EnvVars().db_path)
#     try:
#         with db.connection as conn:


def get_mqtt_config(logger: Logger) -> Optional[MQTTConfig]:
    db = DatabaseManager(EnvVars().db_path)
    try:
        with db.connection as conn:
            cursor = conn.execute("SELECT mqtt_config FROM telemetry LIMIT 1")
            data = cursor.fetchone()
            if not data:
                logger.error("Unable to access MQTT data from telemetry table database.")
                raise ValueError("Unable to access MQTT data from telemetry table database.")
            config = json.loads(data['mqtt_config'])
            return MQTTConfig.from_dict(config)
    except sqlite3.Error as e:
        logger.error(f"Failed to get mqtt data: {e}")
        return None
