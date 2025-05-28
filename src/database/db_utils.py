from typing import Optional
import json
from logging import Logger
import sqlite3

from utils.envvars import EnvVars
from database.database_manager import DatabaseManager
from config.mqtt_config import MQTTConfig
from config.telemetry_config import TelemetryConfig
from config.raptor_config import RaptorConfig


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


def get_telemetry_config(logger: Logger) -> Optional[TelemetryConfig]:
    db = DatabaseManager(EnvVars().db_path)
    try:
        with db.connection as conn:
            cursor = conn.execute("SELECT telemetry_config FROM telemetry_configuration LIMIT 1")
            data = cursor.fetchone()
            if not data:
                logger.error("Unable to access Telemetry data from telemetry_configuration table database.")
                raise ValueError("Unable to access Telemetry data from telemetry_configuration table database.")
            config = json.loads(data['telemetry_config'])
            return TelemetryConfig.from_dict(config)
    except sqlite3.Error as e:
        logger.error(f"Failed to get telemetry config data: {e}")
        return None


def get_mqtt_config(logger: Logger) -> Optional[MQTTConfig]:
    db = DatabaseManager(EnvVars().db_path)
    try:
        with db.connection as conn:
            cursor = conn.execute("SELECT mqtt_config FROM telemetry_configuration LIMIT 1")
            data = cursor.fetchone()
            if not data:
                logger.error("Unable to access MQTT data from telemetry_configuration table database.")
                raise ValueError("Unable to access MQTT data from telemetry_configuration table database.")
            config = json.loads(data['mqtt_config'])
            logger.info(f"Instantiate MQTT config: {config}")
            return MQTTConfig.from_dict(config)
    except sqlite3.Error as e:
        logger.error(f"Failed to get mqtt data: {e}")
        return None


def get_raptor_configuration(logger: Logger) -> Optional[RaptorConfig]:
    db = DatabaseManager(EnvVars().db_path)
    try:
        with db.connection as conn:
            cursor = conn.execute("SELECT raptor_id, firmware_tag, api_key FROM commission LIMIT 1")
            data = cursor.fetchone()
            if not data:
                logger.error("Unable to access MQTT data from telemetry_configuration table database.")
                raise ValueError("Unable to access MQTT data from telemetry_configuration table database.")
            return RaptorConfig.from_dict(data)
    except sqlite3.Error as e:
        logger.error(f"Failed to get Raptor configuration: {e}")
        return None

