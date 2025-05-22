#!/bin/bash
# autosshh.sh - Configure and start system services

APP_DIR="/root/raptor"

echo "Setting up system services..."
echo "reverse-tunnel service..."

# Add host key if not already present
if ! grep -q "54.226.49.65" /root/.ssh/known_hosts 2>/dev/null; then
    echo "Adding host key for 54.226.49.65..."
    ssh-keyscan -H 54.226.49.65 >> /root/.ssh/known_hosts
    chmod 600 /root/.ssh/known_hosts
fi

if [ -f "/etc/systemd/system/reverse-tunnel.service" ]; then
    echo "reverse-tunnel service already exists. Skipping creation."
else

    # Setup reverse-tunnel service
    echo "Setting up reverse-tunnel service..."
    cat > "/etc/systemd/system/reverse-tunnel.service" << EOF
[Unit]
Description=Reverse Tunnel Service
After=network-online.target
Wants=network-online.target
# Add dependency on wlan0 specifically
BindsTo=sys-subsystem-net-devices-wlan0.device
After=sys-subsystem-net-devices-wlan0.device


[Service]
Environment="AUTOSSH_GATETIME=0"
ExecStart=/usr/bin/autossh -M 0 -o "ServerAliveInterval 30" -o "ServerAliveCountMax 3" -o "ExitOnForwardFailure yes" -N -R 0.0.0.0:2002:localhost:8002 -R 0.0.0.0:2022:localhost:22 -i /root/.ssh/CREM3-API-03.pem ubuntu@54.226.49.65
Restart=always
RestartSec=60
StartLimitInterval=200
StartLimitBurst=5


[Install]
WantedBy=multi-user.target
EOF
fi

# Reload systemd to recognize new services
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable and start services
echo "Enabling and starting services..."

# Enable autossh Service
echo "Enabling reverse-tunnel service..."
systemctl enable reverse-tunnel.service
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to enable reverse-tunnel service"
    exit 1
fi

echo "Starting reverse-tunnel service..."
systemctl start reverse-tunnel.service
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to start reverse-tunnel service"
    exit 1
fi

# Check service status
echo "Checking service status..."
systemctl status reverse-tunnel.service --no-pager

echo "Service setup complete!"
exit 0

