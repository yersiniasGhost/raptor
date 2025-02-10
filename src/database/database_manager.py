from typing import Optional
import sqlite3
from sqlite3 import Connection
from utils.singleton import Singleton
from utils.envvars import EnvVars


class DatabaseManager(metaclass=Singleton):

    def __init__(self):
        self.db_path = EnvVars().database_url
        self._connection: Optional[Connection] = None
        self._tsdb_connection: Optional[Connection] = None

    @property
    def connection(self):
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
            self._connection.row_factory = sqlite3.Row
            # Set pragmas
            self._connection.execute('PRAGMA journal_mode=WAL')
            self._connection.execute('PRAGMA synchronous=NORMAL')
        try:
            # Test connection is still good
            self._connection.execute('SELECT 1')
        except (sqlite3.Error, sqlite3.OperationalError):
            # If connection is bad, recreate it
            self._connection = None
            return self.connection
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
            logging.error(f"Database error: {e}")
            self.db.close()  # Force reconnect on next use