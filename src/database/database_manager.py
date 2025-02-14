from typing import Optional, Union
from pathlib import Path
import sqlite3
from sqlite3 import Connection
from utils.singleton import Singleton

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager(metaclass=Singleton):

    def __init__(self, db_path: Union[Path, str], schema_path: Union[Path, str]):
        self.db_path = Path(db_path)
        self.schema_path = Path(schema_path)
        self._connection: Optional[Connection] = None
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def connection(self, retries: int = 3):
        if self._connection is None:
            if retries <= 0:
                raise sqlite3.OperationalError("Failed to connect after maximum retries")

            try:
                logger.info(f"Connecting SQLite3 to :{self.db_path}")
                self._connection = sqlite3.connect(self.db_path)
                self._connection.row_factory = sqlite3.Row
                # Set pragmas
                self._connection.execute('PRAGMA journal_mode=WAL')
                self._connection.execute('PRAGMA synchronous=NORMAL')
                # Test connection is still good
                self._connection.execute('SELECT 1')
            except (sqlite3.Error, sqlite3.OperationalError) as e:
                logger.error(f"Try #{retries}.  Couldn't connect to SQLite3 database: {e}")
                self._connection = None
                return self.connection(retries - 1)
        return self._connection

    def close(self):
        if self._connection:
            self._connection.close()
            self._connection = None

    def __enter__(self):
        """Context manager support"""
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Auto-close on context exit"""
        self.close()

    def init_db(self):
        try:
            with self.connection as conn:
                with open('schema.sql', 'r') as f:
                    conn.executescript(f.read())
                    conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            self.connection.close()
