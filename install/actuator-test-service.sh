#!/bin/bash
# setup_services.sh - Configure and start system services

APP_DIR="/root/raptor"

echo "Setting up system services..."

echo "actuator-stress service..."

if [ -f "/etc/systemd/system/actuator-stress.service" ]; then
    echo "actuator-stress service already exists. Skipping creation."
else

echo "Setting up actuator-stress service..."
cat > "/etc/systemd/system/actuator-stress.service" << EOF
[Unit]
Description=Actuator Stress Test Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/src/jobs/actuator_test.py
Restart=no

[Install]
EOF
fi


# Reload systemd to recognize new services
echo "Reloading systemd daemon..."
systemctl daemon-reload
systemctl disable actuator-stress.service
systemctl status actuator-stress.service --no-pager

echo "Service setup complete!"
exit 0

