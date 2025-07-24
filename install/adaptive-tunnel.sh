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