#!/bin/bash
# autosshh.sh - Configure and start system services

APP_DIR="/root/raptor"

echo "Setting up system services..."
echo "vmc-ui service..."

if [ -f "/etc/systemd/system/reverse-tunnel.service" ]; then
    echo "reverse-tunnel service already exists. Skipping creation."
else

    # Setup reverse-tunnel service
    echo "Setting up reverse-tunnel service..."
    cat > "/etc/systemd/system/reverse-tunnel.service" << EOF
[Unit]
Description=Reverse Tunnel Service
After=network.target

[Service]
Environment="AUTOSSH_GATETIME=0"
ExecStart=/usr/bin/autossh -M 0 -o "ServerAliveInterval 30" -o "ServerAliveCountMax 3" -o "ExitOnForwardFailure yes" -N -R 0.0.0.0:2002:localhost:8002 -i /root/.ssh/CREM3-API-03.pem ubuntu@54.226.49.65
Restart=always
RestartSec=60

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
systemctl status vmc-ui.service --no-pager
systemctl status iot-controller.service --no-pager

echo "Service setup complete!"
exit 0

