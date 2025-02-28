
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
)
-- Devices (specific devices on a hardware instance)
--CREATE TABLE IF NOT EXISTS devices (
--    id INTEGER PRIMARY KEY,
--    hardware_id INTEGER NOT NULL,
--    mac TEXT NOT NULL,
--    config JSON NOT NULL,                   -- Device-specific configuration
--    enabled BOOLEAN DEFAULT true,
--    external_ref TEXT NOT NULL,
--    FOREIGN KEY (hardware_id) REFERENCES hardware(id)
--);
