
-- Hardware Instances (specific hardware configurations)
CREATE TABLE IF NOT EXISTS commission (
    id INTEGER PRIMARY KEY,
    raptor_id CHAR(24) NOT NULL UNIQUE,
    api_key VARCHAR(64) NOT NULL UNIQUE,
    firmware_tag VARCHAR(50),
    CONSTRAINT valid_raptor_id CHECK (LENGTH(raptor_id) = 24)
);

CREATE TABLE IF NOT EXISTS hardware (
    id INTEGER PRIMARY KEY,
    driver_path TEXT NOT NULL,
    name TEXT NOT NULL,                     -- e.g., 'Primary Modbus Bus'
    config JSON NOT NULL,                   -- Store hardware-specific config (port, baud rate, etc.)
    enabled BOOLEAN DEFAULT true,
    external_ref TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Devices (specific devices on a hardware instance)
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY,
    hardware_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    device_id TEXT NOT NULL,                -- e.g., Modbus address or CAN ID
    config JSON NOT NULL,                   -- Device-specific configuration
    enabled BOOLEAN DEFAULT true,
    external_ref TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (hardware_id) REFERENCES hardware(id)
);

-- Device Data Points (specific data points for each device)
CREATE TABLE IF NOT EXISTS device_data_points (
    id INTEGER PRIMARY KEY,
    device_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    data_type TEXT NOT NULL,                -- e.g., 'float', 'int', 'bool'
    access_type TEXT NOT NULL,              -- 'read', 'write', 'read_write'
    address TEXT NOT NULL,                  -- Register address or equivalent
    scaling_factor FLOAT DEFAULT 1.0,
    offset FLOAT DEFAULT 0.0,
    units TEXT,
    external_ref TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES devices(id)
);

-- Create indexes for better query performance
CREATE INDEX idx_data_points_device ON device_data_points(device_id);
CREATE INDEX idx_data_history_point ON data_history(data_point_id);
