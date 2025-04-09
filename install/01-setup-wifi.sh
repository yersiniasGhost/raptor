#!/bin/bash
# setup_wifi.sh - Configure Wi-Fi connectivity

echo "Setting up Wi-Fi connection..."

if [ -z "$1" ]; then
    echo "ERROR: Proper SSID and PASSWD required"
    echo "Usage: $0 <SSID> <PASS>"
    exit 1
fi


# Get Wi-Fi credentials from arguments
WIFI_SSID=${1:-"SSID"}
WIFI_PASSWORD=${2:-"PWD"}

# Check if Wi-Fi is already configured with these credentials
if grep -q "wpa-ssid \"$WIFI_SSID\"" /etc/network/interfaces.d/wlan0 2>/dev/null && \
   grep -q "wpa-psk \"$WIFI_PASSWORD\"" /etc/network/interfaces.d/wlan0 2>/dev/null; then
    echo "Wi-Fi already configured with SSID: $WIFI_SSID. No changes needed."
    exit 0
fi

# Create Wi-Fi configuration file
if [ -n "$WIFI_SSID" ] && [ -n "$WIFI_PASSWORD" ]; then
    cat > "/etc/network/interfaces.d/wlan0" << EOF
allow-hotplug wlan0
iface wlan0 inet dhcp
        wpa-ssid "${WIFI_SSID}"
        wpa-psk "${WIFI_PASSWORD}"
EOF
    echo "Wi-Fi configured with provided credentials: $WIFI_SSID"
    
    # Bring up the wireless interface
    ifdown wlan0 2>/dev/null || true
    ifup wlan0 2>/dev/null || true
    
    # Wait for Wi-Fi connection
    echo "Waiting for Wi-Fi connection..."
    CONNECTED=false
    for i in {1..30}; do
        if ping -c 1 -W 1 8.8.8.8 &>/dev/null; then
            echo "Wi-Fi connection established after $i attempts!"
            CONNECTED=true
            break
        fi
        echo "Waiting for network... ($i/30)"
        sleep 2
    done
    
    if [ "$CONNECTED" = false ]; then
        echo "WARNING: Wi-Fi connection not established. Check credentials and signal strength."
        echo "Continuing with installation..."
        exit 1
    fi
else
    echo "No valid Wi-Fi credentials provided."
    echo "Usage: $0 SSID PASSWORD"
    exit 1
fi

echo "Wi-Fi setup completed successfully."
exit 0
