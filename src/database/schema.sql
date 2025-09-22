
-- Hardware Instances (specific hardware configurations)
CREATE TABLE IF NOT EXISTS commission (
    id INTEGER PRIMARY KEY,
    raptor_id CHAR(24) NOT NULL UNIQUE,
    api_key VARCHAR(64) NOT NULL UNIQUE,
    firmware_tag VARCHAR(50),
    CONSTRAINT valid_raptor_id CHECK (LENGTH(raptor_id) = 24)
);

CREATE TABLE IF NOT EXISTS telemetry_configuration (
    id INTEGER PRIMARY KEY,
    mqtt_config TEXT,
    telemetry_config TEXT
);

CREATE TABLE IF NOT EXISTS hardware (
    id INTEGER PRIMARY KEY,
    hardware_type TEXT NOT NULL,
    driver_path TEXT NOT NULL,
    parameters TEXT NOT NULL,                   -- Store hardware-specific config (port, baud rate, etc.)
    scan_groups TEXT,
    devices TEXT,
    enabled BOOLEAN DEFAULT true,
    external_ref TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry_data (
    id  INTEGER PRIMARY KEY,
    data TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS firmware_status (
    id  INTEGER PRIMARY KEY,
    version_tag TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raptor (
    id INTEGER PRIMARY KEY,
    name TEXT,
    client TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS power_5V (
    id INTEGER PRIMARY KEY,
    requests INTEGER DEFAULT 0,
    CHECK (id = 1)
);

INSERT OR IGNORE INTO power_5V (id, requests) VALUES (1, 0);

DROP TABLE IF EXISTS power_5V;

-- Create new power_requests table
CREATE TABLE IF NOT EXISTS power_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    process_id INTEGER NOT NULL UNIQUE,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_power_requests_process_id ON power_requests(process_id);
CREATE INDEX IF NOT EXISTS idx_power_requests_timestamp ON power_requests(timestamp);

-- Create new database migration table to store migration number, name, and date
CREATE TABLE IF NOT EXISTS database_migration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    migration_id INTEGER NOT NULL UNIQUE,
    migration_info TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP2
);

INSERT OR IGNORE INTO database_migration (migration_id, migration_info) VALUES (1, "Base migration.");

-- Migration 2: Add state management for hardware
-- Create hardware_states table for state change history
CREATE TABLE IF NOT EXISTS hardware_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hardware_id INTEGER NOT NULL,
    state_name TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (hardware_id) REFERENCES hardware (id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_hardware_states_hardware_id ON hardware_states(hardware_id);
CREATE INDEX IF NOT EXISTS idx_hardware_states_timestamp ON hardware_states(timestamp);

INSERT OR IGNORE INTO database_migration (migration_id, migration_info) VALUES (2, "Added state management for hardware operations.");

-- Migration 3: Add exclusive hardware resource locking
-- Create hardware_resource_locks table for exclusive access control
CREATE TABLE IF NOT EXISTS hardware_resource_locks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_key TEXT NOT NULL UNIQUE,
    owner_pid INTEGER NOT NULL,
    acquired_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    lock_info TEXT DEFAULT NULL
);

-- Create hardware_lock_queue table for queued lock requests
CREATE TABLE IF NOT EXISTS hardware_lock_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_key TEXT NOT NULL,
    waiting_pid INTEGER NOT NULL,
    queued_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    timeout_at DATETIME NOT NULL,
    priority INTEGER DEFAULT 0
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_hardware_locks_resource_key ON hardware_resource_locks(resource_key);
CREATE INDEX IF NOT EXISTS idx_hardware_locks_owner_pid ON hardware_resource_locks(owner_pid);
CREATE INDEX IF NOT EXISTS idx_hardware_locks_expires ON hardware_resource_locks(expires_at);
CREATE INDEX IF NOT EXISTS idx_hardware_queue_resource_key ON hardware_lock_queue(resource_key);
CREATE INDEX IF NOT EXISTS idx_hardware_queue_waiting_pid ON hardware_lock_queue(waiting_pid);
CREATE INDEX IF NOT EXISTS idx_hardware_queue_timeout ON hardware_lock_queue(timeout_at);

INSERT OR IGNORE INTO database_migration (migration_id, migration_info) VALUES (3, "Added exclusive hardware resource locking and queuing system.");


