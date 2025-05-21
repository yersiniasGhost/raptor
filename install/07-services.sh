#!/bin/bash
# setup_services.sh - Configure and start system services

APP_DIR="/root/raptor"

echo "Setting up system services..."
echo "vmc-ui service..."

if [ -f "/etc/systemd/system/vmc-ui.service" ]; then
    echo "vmc-ui service already exists. Skipping creation."
else

    # Setup VMC UI service
    echo "Setting up vmc-ui service..."
    cat > "/etc/systemd/system/vmc-ui.service" << EOF
[Unit]
Description=VMC UI API Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/src/api/v2/vmc.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
fi



if [ -f "/etc/systemd/system/iot-controller.service" ]; then
    echo "iot-controller service already exists. Skipping creation."
else

    # Setup IoT Controller service
    echo "Setting up iot-controller service..."
    cat > "/etc/systemd/system/iot-controller.service" << EOF
[Unit]
Description=IoT Controller Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/src/jobs/iot_controller.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
fi


## CMD Controller
if [ -f "/etc/systemd/system/cmd-controller.service" ]; then
    echo "cmd-controller service already exists. Skipping creation."
else

    # Setup cmd Controller service
    echo "Setting up cmd-controller service..."
    cat > "/etc/systemd/system/cmd-controller.service" << EOF
[Unit]
Description=CMD Controller Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/src/jobs/cmd_controller.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
fi


# Reload systemd to recognize new services
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable and start services
echo "Enabling and starting services..."

# VMC UI Service
echo "Enabling vmc-ui service..."
systemctl enable vmc-ui.service
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to enable vmc-ui service"
    exit 1
fi

echo "Starting vmc-ui service..."
systemctl start vmc-ui.service
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to start vmc-ui service"
    exit 1
fi


# CMD UI Service
echo "Enabling cmd-controller service..."
systemctl enable cmd-controller.service
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to enable vmc-ui service"
    exit 1
fi

echo "Starting cmd-controller service..."
systemctl start cmd-controller.service
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to start cmd-controller service"
    exit 1
fi

# IoT Controller Service
echo "Enabling iot-controller service..."
systemctl enable iot-controller.service
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to enable iot-controller service"
    exit 1
fi

echo "Starting iot-controller service..."
systemctl start iot-controller.service
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to start iot-controller service"
    exit 1
fi

# Check service status
echo "Checking service status..."
systemctl status vmc-ui.service --no-pager
systemctl status iot-controller.service --no-pager

echo "Service setup complete!"
exit 0

