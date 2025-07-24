import os
import subprocess
from typing import Tuple
from .base_action import Action
from .action_status import ActionStatus
from config.telemetry_config import TelemetryConfig
from config.mqtt_config import MQTTConfig
from utils import JSON, LogManager


class CreateReverseTunnelServiceAction(Action):

    async def execute(self, telemetry_config: TelemetryConfig,
                      mqtt_config: MQTTConfig) -> Tuple[ActionStatus, JSON]:
        logger = LogManager().get_logger("CreateReverseTunnelServiceAction")
        logger.info("Starting reverse tunnel service creation")
        ui_port = self.params.get("AWS UI port", "2005")
        tunnel_port = self.params.get("AWS SSH Tunnel", "2025")

        try:
            # Step 1: Create the systemd service file
            service_content = f"""[Unit]
Description=Adaptive Reverse Tunnel Service
After=network-online.target NetworkManager.service
Wants=network-online.target
# Wait for any internet connectivity (cellular or WiFi)
After=cellular-init.service

[Service]
Type=forking
Environment="AUTOSSH_GATETIME=0"
ExecStartPre=/usr/local/bin/wait-for-internet.sh
ExecStart=/usr/local/bin/adaptive-tunnel.sh {ui_port} {tunnel_port}
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=60
StartLimitInterval=300
StartLimitBurst=5
KillMode=process

[Install]
WantedBy=multi-user.target
"""

            service_file_path = "/etc/systemd/system/reverse-tunnel.service"

            # Check if we have write permissions to the systemd directory
            systemd_dir = "/etc/systemd/system"
            if not os.access(systemd_dir, os.W_OK):
                logger.error(f"No write permission to {systemd_dir}")
                return ActionStatus.FAILED, {"error": "Insufficient permissions to write systemd service file"}

            # Write the service file
            try:
                with open(service_file_path, 'w') as f:
                    f.write(service_content)
                logger.info(f"Successfully wrote service file to {service_file_path}")
            except IOError as e:
                logger.error(f"Failed to write service file: {e}")
                return ActionStatus.FAILED, {"error": f"Failed to write service file: {str(e)}"}

            # Step 2: Create wait-for-internet script
            wait_script_content = '''#!/bin/bash
# Wait for internet connectivity on any interface

echo "Waiting for internet connectivity..."

for i in {1..60}; do
    # Check cellular first (priority)
    if ip route show dev wwan0 2>/dev/null | grep -q default; then
        if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
            echo "Internet available via cellular (wwan0)"
            exit 0
        fi
    fi

    # Check WiFi as backup
    if ip route show dev wlan0 2>/dev/null | grep -q default; then
        if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
            echo "Internet available via WiFi (wlan0)"
            exit 0
        fi
    fi

    echo "Attempt $i/60: No internet connectivity, waiting..."
    sleep 5
done

echo "ERROR: No internet connectivity after 5 minutes"
exit 1
'''

            wait_script_path = "/usr/local/bin/wait-for-internet.sh"
            try:
                with open(wait_script_path, 'w') as f:
                    f.write(wait_script_content)
                logger.info(f"Successfully wrote wait-for-internet script to {wait_script_path}")
            except IOError as e:
                logger.error(f"Failed to write wait-for-internet script: {e}")
                return ActionStatus.FAILED, {"error": f"Failed to write wait script: {str(e)}"}

            # Step 3: Create adaptive tunnel script
            tunnel_script_content = '''#!/bin/bash
# Adaptive tunnel that uses available connectivity

UI_PORT=$1
TUNNEL_PORT=$2

# Function to get best available interface
get_primary_interface() {
    # Check cellular first (priority)
    if ip route show dev wwan0 2>/dev/null | grep -q default; then
        if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
            echo "wwan0"
            return 0
        fi
    fi

    # Fallback to WiFi
    if ip route show dev wlan0 2>/dev/null | grep -q default; then
        if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
            echo "wlan0"
            return 0
        fi
    fi

    echo "none"
    return 1
}

# Function to get source IP for interface
get_source_ip() {
    local interface=$1
    ip addr show $interface 2>/dev/null | grep "inet " | awk '{print $2}' | cut -d/ -f1 | head -1
}

# Main execution
INTERFACE=$(get_primary_interface)
if [ "$INTERFACE" = "none" ]; then
    echo "ERROR: No internet connectivity available"
    exit 1
fi

SOURCE_IP=$(get_source_ip $INTERFACE)
echo "Starting tunnel via $INTERFACE (IP: $SOURCE_IP)"

# Log the connection method
logger "Reverse tunnel starting via $INTERFACE ($SOURCE_IP)"

# Start autossh with interface binding
exec /usr/bin/autossh -M 0 \\
    -o "ServerAliveInterval 30" \\
    -o "ServerAliveCountMax 3" \\
    -o "ExitOnForwardFailure yes" \\
    -o "BindInterface $INTERFACE" \\
    -N \\
    -R 0.0.0.0:${UI_PORT}:localhost:8002 \\
    -R 0.0.0.0:${TUNNEL_PORT}:localhost:22 \\
    -i /root/.ssh/CREM3-API-03.pem \\
    ubuntu@54.226.49.65
'''

            tunnel_script_path = "/usr/local/bin/adaptive-tunnel.sh"
            try:
                with open(tunnel_script_path, 'w') as f:
                    f.write(tunnel_script_content)
                logger.info(f"Successfully wrote adaptive tunnel script to {tunnel_script_path}")
            except IOError as e:
                logger.error(f"Failed to write adaptive tunnel script: {e}")
                return ActionStatus.FAILED, {"error": f"Failed to write tunnel script: {str(e)}"}

            # Step 4: Make scripts executable
            try:
                os.chmod(wait_script_path, 0o755)
                os.chmod(tunnel_script_path, 0o755)
                logger.info("Successfully made scripts executable")
            except OSError as e:
                logger.error(f"Failed to make scripts executable: {e}")
                return ActionStatus.FAILED, {"error": f"Failed to set script permissions: {str(e)}"}

            # Step 5: Reload systemd daemon to recognize the new service
            try:
                result = subprocess.run(['systemctl', 'daemon-reload'],
                                        capture_output=True, text=True, check=True)
                logger.info("Successfully reloaded systemd daemon")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to reload systemd daemon: {e}")
                return ActionStatus.FAILED, {"error": f"Failed to reload systemd daemon: {str(e)}"}
            except FileNotFoundError:
                logger.error("systemctl command not found")
                return ActionStatus.FAILED, {"error": "systemctl command not available"}

            # Optionally enable the service (uncomment if you want auto-enable)
            # try:
            #     subprocess.run(['systemctl', 'enable', 'reverse-tunnel.service'],
            #                   capture_output=True, text=True, check=True)
            #     logger.info("Successfully enabled reverse-tunnel service")
            # except subprocess.CalledProcessError as e:
            #     logger.warning(f"Failed to enable service (service still created): {e}")

            logger.info("Successfully created reverse tunnel service and scripts")
            return ActionStatus.SUCCESS, {
                "message": "Reverse tunnel service and scripts created successfully",
                "service_file": service_file_path,
                "wait_script": wait_script_path,
                "tunnel_script": tunnel_script_path,
                "ui_port": ui_port,
                "tunnel_port": tunnel_port
            }

        except Exception as e:
            logger.error(f"Unexpected error during service creation: {e}")
            return ActionStatus.FAILED, {"error": f"Unexpected error: {str(e)}"}