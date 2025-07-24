#!/bin/bash
# autosshh.sh - Configure and start system services with adaptive connectivity
# Works with cellular (priority) or WiFi backup

APP_DIR="/root/raptor"
TUNNEL_PORT=${REVERSE_TUNNEL:-2022}
UI_PORT=${VMC_UI_PORT:-2002}
echo "Setting up adaptive system services..."
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

    # Setup adaptive reverse-tunnel service
    echo "Setting up adaptive reverse-tunnel service..."
    cat > "/etc/systemd/system/reverse-tunnel.service" << EOF
[Unit]
Description=Adaptive Reverse Tunnel Service
After=network-online.target NetworkManager.service
Wants=network-online.target
# Wait for any internet connectivity (cellular or WiFi)
After=cellular-init.service

[Service]
Type=forking
Environment="AUTOSSH_GATETIME=0"
ExecStartPre=/usr/local/bin/wait-for-internet.sh
ExecStart=/usr/local/bin/adaptive-tunnel.sh ${UI_PORT} ${TUNNEL_PORT}
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=60
StartLimitInterval=300
StartLimitBurst=5
KillMode=process

[Install]
WantedBy=multi-user.target
EOF

    # Create wait-for-internet script
    cat > "/usr/local/bin/wait-for-internet.sh" << 'EOF'
#!/bin/bash
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
EOF

    # Create adaptive tunnel script
    cat > "/usr/local/bin/adaptive-tunnel.sh" << 'EOF'
#!/bin/bash
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

# Function to bind to specific interface using ip route
bind_to_interface() {
    local interface=$1
    local remote_host=$2

    # Add specific route for the remote host through the desired interface
    local gateway=$(ip route show dev $interface | grep default | awk '{print $3}' | head -1)
    if [ -n "$gateway" ]; then
        # Remove any existing route for this host
        ip route del $remote_host 2>/dev/null || true
        # Add route through specific interface
        ip route add $remote_host via $gateway dev $interface 2>/dev/null || true
    fi
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

# Remote host for routing
REMOTE_HOST="54.226.49.65"

# Bind connection to specific interface
bind_to_interface $INTERFACE $REMOTE_HOST

# Start autossh without interface binding (using routing instead)
exec /usr/bin/autossh -M 0 \\
    -o "ServerAliveInterval 30" \\
    -o "ServerAliveCountMax 3" \\
    -o "ExitOnForwardFailure yes" \\
    -o "StrictHostKeyChecking no" \\
    -o "UserKnownHostsFile /dev/null" \\
    -N \\
    -R 0.0.0.0:${UI_PORT}:localhost:8002 \\
    -R 0.0.0.0:${TUNNEL_PORT}:localhost:22 \\
    -i /root/.ssh/CREM3-API-03.pem \\
    ubuntu@${REMOTE_HOST}
EOF

    # Make scripts executable
    chmod +x /usr/local/bin/wait-for-internet.sh
    chmod +x /usr/local/bin/adaptive-tunnel.sh

fi

# Create interface monitoring service (optional enhancement)
if [ ! -f "/etc/systemd/system/tunnel-monitor.service" ]; then
    echo "Creating tunnel monitoring service..."
    cat > "/etc/systemd/system/tunnel-monitor.service" << 'EOF'
[Unit]
Description=Tunnel Interface Monitor
After=reverse-tunnel.service

[Service]
Type=simple
ExecStart=/usr/local/bin/tunnel-monitor.sh
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

    # Create monitoring script
    cat > "/usr/local/bin/tunnel-monitor.sh" << 'EOF'
#!/bin/bash
# Monitor tunnel connectivity and restart if interface changes

LAST_INTERFACE=""

while true; do
    sleep 30

    # Check if tunnel is running
    if ! systemctl is-active reverse-tunnel.service >/dev/null 2>&1; then
        sleep 30
        continue
    fi

    # Determine current best interface
    CURRENT_INTERFACE="none"

    # Check cellular first
    if ip route show dev wwan0 2>/dev/null | grep -q default; then
        if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
            CURRENT_INTERFACE="wwan0"
        fi
    fi

    # If cellular failed, check WiFi
    if [ "$CURRENT_INTERFACE" = "none" ]; then
        if ip route show dev wlan0 2>/dev/null | grep -q default; then
            if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
                CURRENT_INTERFACE="wlan0"
            fi
        fi
    fi

    # If interface changed or we have cellular back, restart tunnel
    if [ "$CURRENT_INTERFACE" != "$LAST_INTERFACE" ] && [ "$CURRENT_INTERFACE" != "none" ]; then
        # Always prefer cellular - restart if we switched back to cellular
        if [ "$CURRENT_INTERFACE" = "wwan0" ] && [ "$LAST_INTERFACE" != "wwan0" ]; then
            echo "Cellular connectivity restored, switching tunnel to cellular"
            logger "Tunnel monitor: Switching to cellular connectivity"
            systemctl restart reverse-tunnel.service
        elif [ "$LAST_INTERFACE" = "" ]; then
            # First run
            echo "Tunnel monitor started, interface: $CURRENT_INTERFACE"
        elif [ "$CURRENT_INTERFACE" = "wlan0" ] && [ "$LAST_INTERFACE" = "" ]; then
            echo "Tunnel using WiFi backup"
            logger "Tunnel monitor: Using WiFi backup connectivity"
        fi

        LAST_INTERFACE="$CURRENT_INTERFACE"
    fi

    # If no connectivity, log it
    if [ "$CURRENT_INTERFACE" = "none" ]; then
        echo "No internet connectivity available"
        LAST_INTERFACE=""
    fi
done
EOF

    chmod +x /usr/local/bin/tunnel-monitor.sh
fi

# Reload systemd to recognize new services
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable and start services
echo "Enabling and starting services..."

# Enable reverse tunnel service
echo "Enabling reverse-tunnel service..."
systemctl enable reverse-tunnel.service
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to enable reverse-tunnel service"
    exit 1
fi

# Enable tunnel monitor (optional)
echo "Enabling tunnel-monitor service..."
systemctl enable tunnel-monitor.service

echo "Starting reverse-tunnel service..."
systemctl start reverse-tunnel.service
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to start reverse-tunnel service"
    exit 1
fi

echo "Starting tunnel-monitor service..."
systemctl start tunnel-monitor.service

# Check service status
echo "Checking service status..."
echo "=== Reverse Tunnel Service ==="
systemctl status reverse-tunnel.service --no-pager
echo ""
echo "=== Tunnel Monitor Service ==="
systemctl status tunnel-monitor.service --no-pager

echo ""
echo "Adaptive tunnel setup complete!"
echo "• Tunnel will use cellular (wwan0) when available"
echo "• Automatically falls back to WiFi (wlan0) if cellular fails"
echo "• Monitor service switches back to cellular when restored"
echo ""
echo "Check logs with:"
echo "  journalctl -u reverse-tunnel.service -f"
echo "  journalctl -u tunnel-monitor.service -f"

exit 0