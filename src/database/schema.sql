
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


