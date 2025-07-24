#!/bin/bash
# Adaptive tunnel that uses available connectivity

UI_PORT=$1
TUNNEL_PORT=$2

# Enable debugging
set -x

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
        echo "Route added: $remote_host via $gateway dev $interface"
    fi
}

# Validate inputs
if [ -z "$UI_PORT" ] || [ -z "$TUNNEL_PORT" ]; then
    echo "ERROR: Missing port arguments"
    echo "Usage: $0 <UI_PORT> <TUNNEL_PORT>"
    exit 1
fi

# Validate port numbers
if ! [[ "$UI_PORT" =~ ^[0-9]+$ ]] || ! [[ "$TUNNEL_PORT" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Ports must be numeric"
    exit 1
fi

echo "Starting adaptive tunnel with UI_PORT=$UI_PORT, TUNNEL_PORT=$TUNNEL_PORT"

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
REMOTE_USER="ubuntu"

# Test basic connectivity to remote host
echo "Testing connectivity to $REMOTE_HOST..."
if ! ping -c 1 -W 5 $REMOTE_HOST >/dev/null 2>&1; then
    echo "WARNING: Cannot ping remote host $REMOTE_HOST"
fi

# Bind connection to specific interface
bind_to_interface $INTERFACE $REMOTE_HOST

# Check if SSH key exists
SSH_KEY="/root/.ssh/CREM3-API-03.pem"
if [ ! -f "$SSH_KEY" ]; then
    echo "ERROR: SSH key not found at $SSH_KEY"
    exit 1
fi

# Check SSH key permissions
if [ "$(stat -c %a $SSH_KEY)" != "600" ]; then
    echo "WARNING: SSH key permissions are not 600, fixing..."
    chmod 600 "$SSH_KEY"
fi

echo "Starting autossh connection..."
echo "Command: autossh -M 0 -o ServerAliveInterval 30 -o ServerAliveCountMax 3 -o ExitOnForwardFailure yes -o StrictHostKeyChecking no -o UserKnownHostsFile /dev/null -N -R 0.0.0.0:${UI_PORT}:localhost:8002 -R 0.0.0.0:${TUNNEL_PORT}:localhost:22 -i ${SSH_KEY} ${REMOTE_USER}@${REMOTE_HOST}"

# Start autossh with explicit user@host format
exec /usr/bin/autossh -M 0 \\
    -o "ServerAliveInterval 30" \\
    -o "ServerAliveCountMax 3" \\
    -o "ExitOnForwardFailure yes" \\
    -o "StrictHostKeyChecking no" \\
    -o "UserKnownHostsFile /dev/null" \\
    -o "LogLevel VERBOSE" \\
    -N \\
    -R "0.0.0.0:${UI_PORT}:localhost:8002" \\
    -R "0.0.0.0:${TUNNEL_PORT}:localhost:22" \\
    -i "${SSH_KEY}" \\
    "${REMOTE_USER}@${REMOTE_HOST}"