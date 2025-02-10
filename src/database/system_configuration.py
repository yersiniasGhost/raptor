import sqlite3
import json
from utils.envvars import EnvVars


def store_config(config_json):
    """Store JSON configuration into the database."""
    env_vars = EnvVars()
    conn = sqlite3.connect(env_vars.database_url)
    cursor = conn.cursor()
    components = config_json.get("components")
    hardware_data = config_json["hardware"]
    devices = config_json["devices"]

    cursor.execute("INSERT INTO hardware (type, parameters) VALUES (?, ?)",
                   (hardware_data["type"], json.dumps(hardware_data["parameters"])))
    hardware_id = cursor.lastrowid

    for device in devices:
        cursor.execute("INSERT INTO devices (hardware_id, mac, slave_id) VALUES (?, ?, ?)",
                       (hardware_id, device["mac"], device["slave_id"]))

    conn.commit()
    conn.close()


def get_config():
    """Retrieve stored configuration from the database."""
    env_vars = EnvVars()
    conn = sqlite3.connect(env_vars.database_url)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM hardware")
    hardware = [{"id": row[0], "type": row[1], "parameters": json.loads(row[2])} for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM devices")
    devices = [{"id": row[0], "hardware_id": row[1], "mac": row[2], "slave_id": row[3]} for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM system_config")
    config = cursor.fetchone()

    conn.close()

    return {
        "hardware": hardware,
        "devices": devices,
        "system_config": {
            "acquisition_interval": config[1],
            "cloud_url": config[2],
            "warning_action": config[3],
            "error_action": config[4]
        } if config else {}
    }

