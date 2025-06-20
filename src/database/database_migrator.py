#!/usr/bin/env python3

import sqlite3
from typing import List, Tuple

from utils import EnvVars, LogManager


class DatabaseMigrator:

    def __init__(self):
        self.db_path = EnvVars().db_path
        self.logger = LogManager("database_migrator.log").get_logger("DatabaseMigrator")



    def get_current_version(self) -> int:
        """Get current database schema version"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if schema_version table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='schema_version'
            """)

            if not cursor.fetchone():
                # Create schema_version table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE schema_version (
                        version INTEGER PRIMARY KEY,
                        applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        description TEXT
                    )
                """)
                cursor.execute("INSERT INTO schema_version (version, description) VALUES (0, 'Initial schema')")
                conn.commit()
                return 0

            # Get latest version
            cursor.execute("SELECT MAX(version) FROM schema_version")
            result = cursor.fetchone()
            return result[0] if result[0] is not None else 0

        except Exception as e:
            self.logger.error(f"Error getting database version: {e}")
            return 0
        finally:
            conn.close()



    def apply_migration(self, version: int, description: str, sql_statements: List[str]) -> bool:
        """Apply a single migration"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if this version is already applied
            cursor.execute("SELECT version FROM schema_version WHERE version = ?", (version,))
            if cursor.fetchone():
                self.logger.info(f"Migration {version} already applied, skipping")
                return True

            # Apply migration statements
            for sql in sql_statements:
                if sql.strip():  # Skip empty statements
                    cursor.execute(sql)

            # Record migration
            cursor.execute("""
                INSERT INTO schema_version (version, description) 
                VALUES (?, ?)
            """, (version, description))

            conn.commit()
            self.logger.info(f"Applied migration {version}: {description}")
            return True

        except Exception as e:
            self.logger.error(f"Error applying migration {version}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()



    def migrate_to_latest(self) -> bool:
        """Apply all pending migrations"""
        current_version = self.get_current_version()
        self.logger.info(f"Current database version: {current_version}")

        # Define all migrations
        migrations = self.get_migrations()

        success = True
        for version, description, sql_statements in migrations:
            if version > current_version:
                if not self.apply_migration(version, description, sql_statements):
                    success = False
                    break

        if success:
            final_version = self.get_current_version()
            self.logger.info(f"Database migrated to version {final_version}")

        return success



    def get_migrations(self) -> List[Tuple[int, str, List[str]]]:
        """Define all database migrations"""
        return [
            # Migration 1: Add network tables
            (1, "Add network interface and status tables", [
                """CREATE TABLE IF NOT EXISTS network_interfaces (
                    id INTEGER PRIMARY KEY,
                    interface_name VARCHAR(20) NOT NULL,
                    interface_type VARCHAR(20) NOT NULL,
                    enabled BOOLEAN DEFAULT true,
                    priority INTEGER DEFAULT 100,
                    config_type VARCHAR(20) DEFAULT 'dhcp',
                    static_ip VARCHAR(15),
                    static_netmask VARCHAR(15),
                    static_gateway VARCHAR(15),
                    dns_servers TEXT,
                    wireless_ssid VARCHAR(64),
                    wireless_security VARCHAR(20),
                    cellular_apn VARCHAR(64),
                    cellular_operator VARCHAR(32),
                    last_status_check DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(interface_name)
                )""",

                """CREATE TABLE IF NOT EXISTS network_status (
                    id INTEGER PRIMARY KEY,
                    interface_name VARCHAR(20) NOT NULL,
                    is_connected BOOLEAN DEFAULT false,
                    ip_address VARCHAR(15),
                    gateway VARCHAR(15),
                    signal_strength INTEGER,
                    data_usage_rx INTEGER DEFAULT 0,
                    data_usage_tx INTEGER DEFAULT 0,
                    connection_uptime INTEGER DEFAULT 0,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (interface_name) REFERENCES network_interfaces(interface_name)
                )""",

                # Insert default interface configurations
                """INSERT OR IGNORE INTO network_interfaces 
                   (interface_name, interface_type, priority, enabled) VALUES 
                   ('wlan0', 'wireless', 1, true)""",

                """INSERT OR IGNORE INTO network_interfaces 
                   (interface_name, interface_type, priority, enabled, static_ip) VALUES 
                   ('end0', 'ethernet', 2, true, '10.250.250.2/24')""",

                """INSERT OR IGNORE INTO network_interfaces 
                   (interface_name, interface_type, priority, enabled) VALUES 
                   ('end1', 'ethernet', 3, true)"""
            ]),

            # Migration 2: Add SSH tunnel tables
            (2, "Add SSH tunnel configuration and status tables", [
                """CREATE TABLE IF NOT EXISTS ssh_tunnel_config (
                    id INTEGER PRIMARY KEY,
                    tunnel_name VARCHAR(50) NOT NULL UNIQUE,
                    enabled BOOLEAN DEFAULT false,
                    remote_host VARCHAR(255) NOT NULL,
                    remote_port INTEGER NOT NULL,
                    local_port INTEGER DEFAULT 22,
                    ssh_user VARCHAR(64) NOT NULL,
                    ssh_key_path VARCHAR(255),
                    preferred_interface VARCHAR(20),
                    auto_reconnect BOOLEAN DEFAULT true,
                    reconnect_interval INTEGER DEFAULT 30,
                    max_reconnect_attempts INTEGER DEFAULT 10,
                    keepalive_interval INTEGER DEFAULT 60,
                    FOREIGN KEY (preferred_interface) REFERENCES network_interfaces(interface_name)
                )""",

                """CREATE TABLE IF NOT EXISTS ssh_tunnel_status (
                    id INTEGER PRIMARY KEY,
                    tunnel_name VARCHAR(50) NOT NULL,
                    is_active BOOLEAN DEFAULT false,
                    current_interface VARCHAR(20),
                    connection_start DATETIME,
                    last_keepalive DATETIME,
                    reconnect_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    pid INTEGER,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tunnel_name) REFERENCES ssh_tunnel_config(tunnel_name),
                    FOREIGN KEY (current_interface) REFERENCES network_interfaces(interface_name)
                )""",

                # Insert default tunnel configuration
                """INSERT OR IGNORE INTO ssh_tunnel_config 
                   (tunnel_name, enabled, remote_host, remote_port, ssh_user, preferred_interface) VALUES 
                   ('main_tunnel', false, 'your-aws-server.com', 2201, 'tunnel-user', 'wlan0')"""
            ]),

            # Migration 3: Add network events table
            (3, "Add network events logging table", [
                """CREATE TABLE IF NOT EXISTS network_events (
                    id INTEGER PRIMARY KEY,
                    event_type VARCHAR(50) NOT NULL,
                    interface_name VARCHAR(20),
                    tunnel_name VARCHAR(50),
                    description TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (interface_name) REFERENCES network_interfaces(interface_name),
                    FOREIGN KEY (tunnel_name) REFERENCES ssh_tunnel_config(tunnel_name)
                )"""
            ])
        ]


# Example usage and migration runner
def run_migrations(db_path: str = "/opt/iot_device/data/device.db"):
    """Run database migrations"""
    logging.basicConfig(level=logging.INFO)

    migrator = DatabaseMigrator(db_path)

    if migrator.migrate_to_latest():
        print("Database migrations completed successfully")
        return True
    else:
        print("Database migrations failed")
        return False


if __name__ == "__main__":
    import sys

    db_path = sys.argv[1] if len(sys.argv) > 1 else "/opt/iot_device/data/device.db"
    run_migrations(db_path)