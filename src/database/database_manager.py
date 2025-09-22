from typing import Optional, Dict, Any, Iterable, List, Tuple
from pathlib import Path
import sqlite3
from sqlite3 import Connection
from utils import EnvVars, Singleton
import time
import shutil

from utils import LogManager
import json


class DatabaseManager(metaclass=Singleton):

    def __init__(self):
        self.logger = LogManager().get_logger("DatabaseManager")
        self.db_path = Path(EnvVars().db_path)
        self.schema_path = Path(EnvVars().schema_path)
        self._connection: Optional[Connection] = None
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def connection(self, retries: int = 3):
        if self._connection is None:
            if retries <= 0:
                raise sqlite3.OperationalError("Failed to connect after maximum retries")

            try:
                self.logger.info(f"Connecting SQLite3 to :{self.db_path}")
                self._connection = sqlite3.connect(self.db_path)
                self._connection.row_factory = sqlite3.Row
                # Set pragmas
                self._connection.execute('PRAGMA journal_mode=WAL')
                self._connection.execute('PRAGMA synchronous=NORMAL')
                # Test connection is still good
                self._connection.execute('SELECT 1')
            except (sqlite3.Error, sqlite3.OperationalError) as e:
                self.logger.error(f"Try #{retries}.  Couldn't connect to SQLite3 database: {e}")
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



    def add_power_request(self, process_id: int) -> bool:
        """
        Add a power request for a specific process ID.
        Returns:
            bool: True if this is the first power request (power should be turned on),
                  False if there were already existing requests
        """
        try:
            cursor = self.connection.cursor()
            # Check if any requests exist before adding
            cursor.execute("SELECT COUNT(*) FROM power_requests")
            existing_count = cursor.fetchone()[0]

            # Insert the new request
            cursor.execute("""
                INSERT OR IGNORE INTO power_requests (process_id, timestamp)
                VALUES (?, CURRENT_TIMESTAMP)
            """, (process_id,))

            self.connection.commit()
            # Return True if this was the first request
            return existing_count == 0
        except sqlite3.Error as e:
            self.connection.rollback()
            self.logger.error(f"Error Adding power on request: {e}")
            raise



    def remove_power_request(self, process_id: int) -> bool:
        """
        Remove a power request for a specific process ID.

        Args:
            process_id: The process ID that no longer needs power

        Returns:
            bool: True if this was the last power request (power should be turned off),
                  False if there are still other requests
        """
        try:
            cursor = self.connection.cursor()
            # Remove the request
            cursor.execute("""
                DELETE FROM power_requests WHERE process_id = ?
            """, (process_id,))

            self.connection.commit()

            # Check if any requests remain
            cursor.execute("SELECT COUNT(*) FROM power_requests")
            remaining_count = cursor.fetchone()[0]

            # Return True if no requests remain
            return remaining_count == 0
        except sqlite3.Error as e:
            self.connection.rollback()
            self.logger.error(f"Error Removing power request: {e}")
            raise



    def get_power_requests(self) -> List[int]:
        """
        Get all current power request process IDs.
        Returns:
            List[int]: List of process IDs that have active power requests
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT process_id FROM power_requests ORDER BY timestamp")
        results = cursor.fetchall()
        return [row[0] for row in results]



    def clear_all_power_requests(self):
        """Clear all power requests (useful for initialization/cleanup)"""
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM power_requests")
        self.connection.commit()
        self.logger.info("Cleared all power requests")



    def get_power_request_count(self) -> int:
        """Get the current number of active power requests"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM power_requests")
        return cursor.fetchone()[0]

    def clear_existing_configuration(self):
        """ Clear the existing configuration data.  Keep the telemetry data in case of roll back? """
        try:
            cursor = self.connection.cursor()
            # Delete all rows from telemetry table
            cursor.execute("DELETE FROM telemetry_configuration")
            cursor.execute("DELETE FROM hardware")
            self.logger.info("TOD: Deleting rows from db")

        except sqlite3.Error as e:
            self.connection.rollback()
            self.logger.error(f"Error clearing existing configuration: {e}")
            raise


    def update_telemetry(self, telemetry_config: str, mqtt_config: str):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                            INSERT INTO telemetry_configuration (mqtt_config, telemetry_config)
                            VALUES (?, ?)
                        """, (mqtt_config, telemetry_config))
            self.logger.info("TOD: Inserted telemetry and mqtt config.")
        except Exception as e:
            self.connection.rollback()
            self.logger.error(f"Error inserting telemetry/mqtt configuration: {e}")
            raise

    def add_raptor(self, raptor_config: Dict[str, str]):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO raptor
                (id, name, client)
                VALUES (1, ?, ?)
                """, (raptor_config.get("name", "NO Location"),
                      raptor_config.get("client", "NO Client")))
        except sqlite3.Error as e:
            self.connection.rollback()
            self.logger.error(f"Database error: {e}")
            raise

        except Exception as e:
            self.connection.rollback()
            self.logger.error(f"Error processing configuration: {e}")
            raise


    def reset_power_requests(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Increment the counter
            cursor.execute("""
                DELETE FROM power_requests;
            """)
            conn.commit()
            # Get the updated value
            return 0


    def get_raptor(self) -> Optional[Dict[str, str]]:
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT name, client, timestamp FROM raptor ORDER BY timestamp DESC LIMIT 1
            """)
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            self.logger.error(f"Error retrieving raptor data: {e}")
            raise

    def add_hardware(self, hardware_configuration: Dict[str, Any]):

        try:
            cursor = self.connection.cursor()
            for hw_name, hw_config_list in hardware_configuration.items():
                for the_hardware in hw_config_list:
                    cursor.execute("""
                            INSERT INTO hardware 
                            (hardware_type, driver_path, parameters, scan_groups, devices, external_ref)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                        hw_name,
                        the_hardware['driver_path'],
                        json.dumps(the_hardware["parameters"]),
                        json.dumps(the_hardware.get("scan_groups", [])),
                        json.dumps(the_hardware.get("devices")),
                        the_hardware.get("crem3_id")
                    ))
                    self.logger.info(f":q"
                                     f"Inserting: {hw_name}")
            self.connection.commit()
            self.logger.info("TOD:  Inserted into hardware table.")
            cursor = self.connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM hardware")
            # Fetch the result (will be a tuple with one item)
            count = cursor.fetchone()[0]
            self.logger.info(f"Total row count: {count}")
            return True

        except sqlite3.Error as e:
            self.connection.rollback()
            self.logger.error(f"Database error: {e}")
            raise

        except Exception as e:
            self.connection.rollback()
            self.logger.error(f"Error processing configuration: {e}")
            raise


    def clear_telemetry_data(self):
        try:
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM telemetry_data")
            self.connection.commit()
        except sqlite3.Error as e:
            self.connection.rollback()
            self.logger.error(f"Error clearing telemetry data: {e}")
            raise

    def remove_stored_telemetry_data(self, ids: List[int]):
        try:
            cursor = self.connection.cursor()
            if not ids:
                return

            # Create placeholders for the IN clause
            placeholders = ','.join('?' * len(ids))
            cursor.execute(f"DELETE FROM telemetry_data WHERE id IN ({placeholders})", ids)
            self.connection.commit()

            deleted_count = cursor.rowcount
            self.logger.info(f"Deleted {deleted_count} telemetry data rows.")

        except sqlite3.Error as e:
            self.logger.error(f"Database error removing telemetry data: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error removing telemetry data: {e}")
            raise


    def count_stored_telemetry_data(self) -> int:
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM telemetry_data")
            count = cursor.fetchone()[0]
            return count

        except sqlite3.Error as e:
            self.logger.error(f"Database error counting telemetry data: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error counting telemetry data: {e}")
            raise


    def get_stored_telemetry_data(self, back_log_limit: int = 200) -> Tuple[List[Dict[str, Any]], List[int]]:
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT id, data, timestamp FROM telemetry_data ORDER BY timestamp DESC LIMIT ?",
                           (back_log_limit,))
            rows = cursor.fetchall()

            result = []
            row_ids = []

            for row in rows:
                row_id, data_json, timestamp = row
                telemetry_data = json.loads(data_json)
                # Add metadata from the database
                telemetry_data['timestamp'] = timestamp
                result.append(telemetry_data)
                row_ids.append(row_id)

            lr = len(result)
            if lr > 1:
                self.logger.info(f"Collected backlog {lr} rows of telemetry data.")
            return result, row_ids

        except sqlite3.Error as e:
            self.logger.error(f"Database error reading telemetry data: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error reading telemetry data: {e}")
            raise

    def store_telemetry_data(self, telemetry_data: Dict[str, Any]):
        try:
            cursor = self.connection.cursor()
            data_json = json.dumps(telemetry_data)
            cursor.execute(
                "INSERT INTO telemetry_data (data) VALUES (?)",
                (data_json,)
            )
            self.connection.commit()
        except sqlite3.Error as e:
            self.connection.rollback()
            self.logger.error(f"Database error writing telemetry data: {e}")
            raise
        except Exception as e:
            self.connection.rollback()
            self.logger.error(f"Error writing telemetry data: {e}")
            raise



    def get_hardware_systems(self, system: str) -> Iterable[dict]:
        """
        Iterate through each instance of hardware for the given system type "BMS", "Converters", etc.
        Return a dictionary of data for each column.
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
             SELECT id, hardware_type, driver_path, parameters, scan_groups, 
                       devices, enabled, external_ref 
                FROM hardware 
                WHERE hardware_type LIKE ?
            """, (f'%{system}%',))

            columns = [description[0] for description in cursor.description]
            for row in cursor.fetchall():
                config = dict(zip(columns, row))
                config['parameters'] = json.loads(config['parameters'])
                config['scan_groups'] = json.loads(config['scan_groups'])
                config['devices'] = json.loads(config['devices'])
                config['parameters']['hardware_id'] = config['id']
                yield config

        except sqlite3.Error as e:
            self.logger.error(f"Database error retrieving {system} hardware: {e}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error: {e}")
            raise

    def get_current_firmware_version(self) -> Optional[Dict[str, str]]:
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT version_tag, timestamp FROM firmware_status ORDER BY timestamp DESC LIMIT 1
            """)
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            self.logger.error(f"Error retrieving last version: {e}")
            raise

    def add_firmware_version(self, version_tag: str):
        try:
            cursor = self.connection.cursor()
            # Using CURRENT_TIMESTAMP for the timestamp value
            cursor.execute("""
                   INSERT INTO firmware_status (version_tag, timestamp)
                   VALUES (?, CURRENT_TIMESTAMP)
               """, (version_tag,))
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            self.logger.error(f"Error inserting new version: {e}")
            raise

    def get_all_firmware_versions(self) -> List[Dict[str, str]]:
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT id, version_tag, timestamp
                FROM firmware_status
                ORDER BY timestamp DESC
            """)
            results = cursor.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            self.logger.error(f"Error retrieving all versions: {e}")
            raise

    def rebuild_db(self, backup: bool = True) -> bool:
        """
        Rebuilds the database from scratch using the schema file.
        """
        self.logger.info("Starting database rebuild process")

        # Close any existing connection
        self.close()

        try:
            # Create backup if requested
            if backup and self.db_path.exists():
                backup_path = self.db_path.with_suffix(f'.bak.{int(time.time())}')
                self.logger.info(f"Creating backup at {backup_path}")
                shutil.copy2(self.db_path, backup_path)

            # Remove existing database file
            if self.db_path.exists():
                self.logger.info("Removing existing database file")
                self.db_path.unlink()

            # Ensure parent directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Create new database and initialize schema
            self.logger.info("Creating new database with schema")
            with sqlite3.connect(self.db_path) as temp_conn:
                temp_conn.row_factory = sqlite3.Row

                # Set WAL mode and other pragmas
                temp_conn.execute('PRAGMA journal_mode=WAL')
                temp_conn.execute('PRAGMA synchronous=NORMAL')

                # Read and execute schema
                if not self.schema_path.exists():
                    raise FileNotFoundError(f"Schema file not found: {self.schema_path}")

                with open(self.schema_path, 'r') as f:
                    schema_sql = f.read()
                    temp_conn.executescript(schema_sql)

                # Verify schema was created by checking for tables
                cursor = temp_conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                tables = cursor.fetchall()
                if not tables:
                    raise sqlite3.Error("No tables created from schema")

                temp_conn.commit()

            # Reset the connection property
            self._connection = None
            self.logger.info("Database rebuild completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to rebuild database: {e}")
            # If backup exists and rebuild failed, try to restore
            if backup and 'backup_path' in locals():
                try:
                    self.logger.info("Attempting to restore from backup")
                    if self.db_path.exists():
                        self.db_path.unlink()
                    shutil.copy2(backup_path, self.db_path)
                    self.logger.info("Restored from backup successfully")
                except Exception as restore_error:
                    self.logger.error(f"Failed to restore from backup: {restore_error}")

            self._connection = None
            return False



    def run_schema_sql(self) -> bool:
        """
        Execute the schema.sql file on the database.
        This will create/update tables and indexes as defined in the schema file.

        Returns:
            bool: True if schema was applied successfully, False otherwise
        """
        try:
            if not self.schema_path.exists():
                self.logger.error(f"Schema file not found: {self.schema_path}")
                return False

            self.logger.info(f"Applying schema from {self.schema_path}")

            with open(self.schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()

            if not schema_sql.strip():
                self.logger.error("Schema file is empty")
                return False

            conn = self.connection
            conn.row_factory = sqlite3.Row

            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA foreign_keys=ON')

            conn.executescript(schema_sql)

            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            tables = [row[0] for row in cursor.fetchall()]

            if tables:
                self.logger.info(f"Schema applied successfully. Created/updated tables: {', '.join(tables)}")
            else:
                self.logger.warning("Schema applied but no tables found")
            conn.commit()
            self.close()
            return True

        except sqlite3.Error as e:
            self.logger.error(f"Database error applying schema: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error applying schema: {e}")
            return False

    def get_latest_migration(self) -> Tuple[int, str]:
        try:
            cursor = self.connection.execute("""
                            SELECT migration_id, migration_info FROM database_migration
                            ORDER BY id DESC
                            LIMIT 1; 
                        """)
            results = cursor.fetchall()
            if not results:
                return 0, "Very old migration"
            row = results[0]
            return row[0], row[1]
        except Exception as e:
            return 0, f"Error or no migrations.  {e}"
