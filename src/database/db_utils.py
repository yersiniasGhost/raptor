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
    db = DatabaseManager()
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
    db = DatabaseManager()
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
    db = DatabaseManager()
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
    db = DatabaseManager()
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


def add_hardware_state(hardware_id: int, state_name: str, logger: Logger) -> bool:
    """Add a new hardware state change to the database"""
    db = DatabaseManager()
    try:
        with db.connection as conn:
            cursor = conn.execute(
                "INSERT INTO hardware_states (hardware_id, state_name) VALUES (?, ?)",
                (hardware_id, state_name)
            )
            conn.commit()
            logger.info(f"Added hardware state: {state_name} for hardware {hardware_id}")
            return True
    except sqlite3.Error as e:
        logger.error(f"Failed to add hardware state: {e}")
        return False


def get_current_hardware_state(hardware_id: int, logger: Logger) -> Optional[str]:
    """Get the current state for a hardware device"""
    db = DatabaseManager()
    try:
        with db.connection as conn:
            cursor = conn.execute(
                "SELECT state_name FROM hardware_states WHERE hardware_id = ? ORDER BY timestamp DESC LIMIT 1",
                (hardware_id,)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    except sqlite3.Error as e:
        logger.error(f"Failed to get current hardware state: {e}")
        return None


def get_hardware_state_history(hardware_id: int, limit: int = 10, logger: Logger = None) -> List[Dict[str, str]]:
    """Get the state change history for a hardware device"""
    db = DatabaseManager()
    try:
        with db.connection as conn:
            cursor = conn.execute(
                "SELECT state_name, timestamp FROM hardware_states WHERE hardware_id = ? ORDER BY timestamp DESC LIMIT ?",
                (hardware_id, limit)
            )
            results = cursor.fetchall()
            return [{"state_name": row[0], "timestamp": row[1]} for row in results]
    except sqlite3.Error as e:
        if logger:
            logger.error(f"Failed to get hardware state history: {e}")
        return []


def get_previous_hardware_state(hardware_id: int, logger: Logger) -> Optional[str]:
    """Get the previous state for a hardware device (second most recent)"""
    db = DatabaseManager()
    try:
        with db.connection as conn:
            cursor = conn.execute(
                "SELECT state_name FROM hardware_states WHERE hardware_id = ? ORDER BY timestamp DESC LIMIT 2",
                (hardware_id,)
            )
            results = cursor.fetchall()
            # Return the second most recent state (index 1) if it exists
            return results[1][0] if len(results) > 1 else None
    except sqlite3.Error as e:
        logger.error(f"Failed to get previous hardware state: {e}")
        return None

