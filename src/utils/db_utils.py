import logging
import sqlite3

from .envvars import EnvVars
from database.database_manager import DatabaseManager


def get_api_key(logger: logging.Logger = logging.getLogger(__name__)):
    db = DatabaseManager(EnvVars().db_path)
    try:
        with db.connection as conn:
            cursor = conn.execute("SELECT * FROM commission LIMIT 1")
            data = cursor.fetchone()
            if data:
                return data['api_key']
            else:
                logger.error("Unable to access commission database.")
                raise ValueError(f"Unable to access commission data.")
    except sqlite3.Error as e:
        logger.error(f"Failed to get commission data: {e}")
        return None
