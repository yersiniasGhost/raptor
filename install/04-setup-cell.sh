#!/bin/bash
# Complete Network Setup for TS-7180
# Manages: Cellular (wwan0), WiFi (wlan0), and protects Modbus interfaces (end0/end1)
# Phase 1: One-time configuration
# Phase 2: Hardware initialization only (NetworkManager handles the rest)

if [ "$1" = "configure" ]; then
    echo "=== Complete Network Configuration ==="

    if [ "$EUID" -ne 0 ]; then
        echo "Please run as root: sudo $0 configure"
        exit 1
    fi

    echo "Step 1: Installing packages..."
    apt update -qq
    apt install -y libmbim-utils network-manager

    echo "Step 2: Configuring NetworkManager to manage all interfaces..."

    # Backup original NetworkManager config
    cp /etc/NetworkManager/NetworkManager.conf /etc/NetworkManager/NetworkManager.conf.backup

    # Configure NetworkManager to manage all interfaces including those from ifupdown
    cat > /etc/NetworkManager/NetworkManager.conf << 'EOF'
[main]
plugins=ifupdown,keyfile

[ifupdown]
managed=true

[device]
# Ensure WiFi devices are always managed
match-device=type:wifi
managed=true
EOF

    echo "Step 3: Hardware setup and modem configuration..."
    # Power up modem
    gpioset 5 17=1; sleep 20
    gpioset 2 12=0; sleep 20
    gpioset 2 19=1; sleep 5; gpioset 2 19=0
    echo "Waiting for modem boot..."
    sleep 60

    # Configure UART and set MBIM mode
    tshwctl --addr 307 --poke 1
    stty -F /dev/ttymxc2 115200 cs8 -parenb -cstopb -echo -onlcr

    echo "Configuring modem for MBIM..."
    python3 -c "
import serial, time
ser = serial.Serial('/dev/ttymxc2', 115200, timeout=5)
def at(cmd): ser.write(f'{cmd}\r\n'.encode()); time.sleep(2); return ser.read_all().decode('utf-8', errors='ignore')
at('AT+CGDCONT=1,\"IP\",\"iot.aer.net\"')
at('AT#USBCFG=3')
at('AT#RESET')
ser.close()
"
    echo "Waiting for modem reset..."
    sleep 60

    echo "Step 4: Starting NetworkManager and ModemManager..."
    # Stop wpa_supplicant so NetworkManager can take over WiFi
    systemctl stop wpa_supplicant 2>/dev/null || true
    systemctl disable wpa_supplicant 2>/dev/null || true

    systemctl restart NetworkManager ModemManager
    sleep 15

    echo "Step 5: Configuring network priorities..."

    # Wait for modem detection
    echo "Waiting for cellular modem detection..."
    for i in {1..30}; do
        if mmcli -L 2>/dev/null | grep -q Modem; then
            echo "Modem detected!"
            break
        fi
        echo "  Attempt $i/30..."
        sleep 2
    done

    # Create cellular connection as primary internet with highest priority
    echo "Creating cellular connection as primary internet..."
    nmcli connection delete cellular 2>/dev/null || true
    nmcli connection add type gsm con-name cellular apn iot.aer.net
    nmcli connection modify cellular connection.autoconnect yes
    nmcli connection modify cellular connection.autoconnect-priority 100
    nmcli connection modify cellular ipv4.route-metric 50

    # Configure Modbus interfaces to never handle internet traffic
    echo "Protecting Modbus interfaces from internet traffic..."
    if nmcli connection show end0 >/dev/null 2>&1; then
        nmcli connection modify end0 ipv4.never-default yes
        nmcli connection modify end0 connection.autoconnect-priority -10
    fi

    if nmcli connection show end1 >/dev/null 2>&1; then
        nmcli connection modify end1 ipv4.never-default yes
        nmcli connection modify end1 connection.autoconnect-priority -10
    fi

    # Configure WiFi to be backup only (when available)
    echo "Configuring WiFi as backup internet (when available)..."
    echo "Note: WiFi will only be used when cellular is unavailable."
    echo "      Cellular is prioritized for reliability in remote deployments."

    echo "Step 6: Creating minimal hardware init service..."

    # Create minimal hardware init script
    cat > /usr/local/bin/cellular-init.sh << 'EOF'
#!/bin/bash
# Minimal hardware initialization for cellular modem
# NetworkManager handles the actual connection

echo "Initializing cellular modem hardware..."

# Power up modem
gpioset 5 17=1
sleep 20
gpioset 2 12=0
sleep 20
gpioset 2 19=1
sleep 5
gpioset 2 19=0

# Configure UART
tshwctl --addr 307 --poke 1
stty -F /dev/ttymxc2 115200 cs8 -parenb -cstopb -echo -onlcr

echo "Cellular modem hardware ready"
# NetworkManager will handle the connection automatically
EOF

    chmod +x /usr/local/bin/cellular-init.sh

    # Create systemd service for hardware init only
    cat > /etc/systemd/system/cellular-init.service << 'EOF'
[Unit]
Description=Cellular Modem Hardware Initialization
Before=NetworkManager.service
DefaultDependencies=false

[Service]
Type=oneshot
ExecStart=/usr/local/bin/cellular-init.sh
RemainAfterExit=yes
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable cellular-init.service
    systemctl enable NetworkManager

    echo "✅ Configuration complete!"
    echo "   • NetworkManager now manages all interfaces"
    echo "   • Cellular: Primary internet (metric 50, autoconnect priority 100)"
    echo "   • WiFi: Backup internet only (metric 300 when connected)"
    echo "   • end0/end1: Protected from internet traffic (never-default)"
    echo "   • wpa_supplicant: Disabled (NetworkManager handles WiFi)"
    echo ""
    echo "DEPLOYMENT NOTES:"
    echo "   • Cellular will be the primary internet connection"
    echo "   • WiFi is optional and only used as backup when cellular fails"
    echo "   • System designed to work reliably without WiFi/router"
    echo ""
    echo "Optional WiFi setup (only if router available):"
    echo "   nmcli device wifi connect 'SSID' password 'PASSWORD'"
    echo ""
    echo "Reboot to test: sudo reboot"

elif [ "$1" = "wifi" ]; then
    if [ -z "$2" ] || [ -z "$3" ]; then
        echo "Usage: $0 wifi SSID PASSWORD"
        echo "Example: $0 wifi 'MofiNetworkB3C' 'pass_mofi'"
        exit 1
    fi

    SSID="$2"
    PASSWORD="$3"

    echo "=== Connecting to WiFi: $SSID ==="

    # Connect to WiFi and set it as backup priority
    nmcli device wifi connect "$SSID" password "$PASSWORD"

    # Set WiFi as backup priority (higher metric = lower priority)
    WIFI_CONNECTION=$(nmcli -t -f NAME,DEVICE connection show --active | grep wlan0 | cut -d: -f1)
    if [ -n "$WIFI_CONNECTION" ]; then
        nmcli connection modify "$WIFI_CONNECTION" ipv4.route-metric 300
        nmcli connection modify "$WIFI_CONNECTION" connection.autoconnect-priority 50
        echo "✅ WiFi connected and configured as backup internet connection"
        echo "    Cellular remains primary - WiFi only used if cellular fails"
    else
        echo "❌ WiFi connection failed"
    fi

elif [ "$1" = "priority" ]; then
    echo "=== Setting Network Priority ==="

    if [ "$2" = "cellular" ]; then
        echo "Setting cellular as primary internet connection..."
        nmcli connection modify cellular ipv4.route-metric 50
        nmcli connection modify cellular connection.autoconnect-priority 100

        # Set any WiFi connections as backup
        for conn in $(nmcli -t -f NAME,TYPE connection show | grep wifi | cut -d: -f1); do
            nmcli connection modify "$conn" ipv4.route-metric 300
            nmcli connection modify "$conn" connection.autoconnect-priority 50
        done
        echo "✅ Cellular set as primary (recommended for remote deployments)"

    elif [ "$2" = "wifi" ]; then
        echo "Setting WiFi as primary internet connection..."
        nmcli connection modify cellular ipv4.route-metric 300
        nmcli connection modify cellular connection.autoconnect-priority 50

        # Set WiFi connections as primary
        for conn in $(nmcli -t -f NAME,TYPE connection show | grep wifi | cut -d: -f1); do
            nmcli connection modify "$conn" ipv4.route-metric 50
            nmcli connection modify "$conn" connection.autoconnect-priority 100
        done
        echo "✅ WiFi set as primary"
        echo "⚠️  Warning: This may cause issues in deployments without reliable WiFi"
    else
        echo "Usage: $0 priority [cellular|wifi]"
        echo "Note: Cellular is recommended as primary for remote deployments"
        exit 1
    fi

elif [ "$1" = "test" ]; then
    echo "=== Testing Complete Network Status ==="

    echo "Hardware status:"
    echo "  USB modem: $(lsusb | grep -i telit >/dev/null && echo 'detected' || echo 'not found')"
    echo "  MBIM device: $([ -c /dev/cdc-wdm0 ] && echo 'available' || echo 'not available')"
    echo "  wwan0 interface: $(ip link show wwan0 >/dev/null 2>&1 && echo 'exists' || echo 'missing')"
    echo "  wlan0 interface: $(ip link show wlan0 >/dev/null 2>&1 && echo 'exists' || echo 'missing')"

    echo "Service status:"
    echo "  cellular-init: $(systemctl is-active cellular-init 2>/dev/null || echo 'inactive')"
    echo "  NetworkManager: $(systemctl is-active NetworkManager 2>/dev/null || echo 'inactive')"
    echo "  ModemManager: $(systemctl is-active ModemManager 2>/dev/null || echo 'inactive')"
    echo "  wpa_supplicant: $(systemctl is-active wpa_supplicant 2>/dev/null || echo 'disabled')"

    echo "NetworkManager device status:"
    nmcli device status

    echo "Active connections:"
    nmcli connection show --active

    echo "Routing table:"
    ip route show

    echo "Connection priorities and metrics:"
    if nmcli connection show cellular >/dev/null 2>&1; then
        CELL_METRIC=$(nmcli connection show cellular | grep ipv4.route-metric | awk '{print $2}')
        CELL_PRIORITY=$(nmcli connection show cellular | grep autoconnect-priority | awk '{print $2}')
        echo "  Cellular: metric=$CELL_METRIC, priority=$CELL_PRIORITY"
    fi

    for conn in $(nmcli -t -f NAME,TYPE connection show | grep wifi | cut -d: -f1); do
        WIFI_METRIC=$(nmcli connection show "$conn" | grep ipv4.route-metric | awk '{print $2}')
        WIFI_PRIORITY=$(nmcli connection show "$conn" | grep autoconnect-priority | awk '{print $2}')
        echo "  WiFi ($conn): metric=$WIFI_METRIC, priority=$WIFI_PRIORITY"
    done

    echo "Internet connectivity test:"
    if ping -c 1 8.8.8.8 >/dev/null 2>&1; then
        ROUTE=$(ip route get 8.8.8.8 | head -1)
        echo "✅ Internet connectivity: OK via $ROUTE"
    else
        echo "❌ Internet connectivity: Failed"
        echo "    Check: 1) Cellular signal, 2) APN settings, 3) SIM card"
    fi

    echo "WiFi status:"
    if nmcli device status | grep -q "wlan0.*connected"; then
        echo "✅ WiFi: Connected (backup internet available)"
    elif nmcli device status | grep -q "wlan0.*disconnected"; then
        echo "ℹ️  WiFi: Available but not connected"
    else
        echo "ℹ️  WiFi: Not available (normal for remote deployments)"
    fi

elif [ "$1" = "connect" ]; then
    echo "=== Manually Activating Cellular Connection ==="
    sudo nmcli connection up cellular

elif [ "$1" = "disconnect" ]; then
    echo "=== Disconnecting Cellular Connection ==="
    sudo nmcli connection down cellular

elif [ "$1" = "logs" ]; then
    echo "=== Network Service Logs ==="
    echo "Hardware init logs:"
    journalctl -u cellular-init --no-pager -n 20
    echo
    echo "NetworkManager logs:"
    journalctl -u NetworkManager --no-pager -n 15 | grep -E "(cellular|wifi|wlan0|wwan0)"

else
    echo "TS-7180 Complete Network Setup"
    echo "=============================="
    echo
    echo "Usage:"
    echo "  $0 configure                    # One-time setup (run as root)"
    echo "  $0 wifi 'SSID' 'PASSWORD'      # Connect to WiFi"
    echo "  $0 priority [cellular|wifi]    # Set internet priority"
    echo "  $0 test                         # Check current status"
    echo "  $0 connect                      # Manually connect cellular"
    echo "  $0 disconnect                   # Manually disconnect cellular"
    echo "  $0 logs                         # View service logs"
    echo
    echo "Normal workflow:"
    echo "  1. sudo $0 configure                          # Once during setup"
    echo "  2. sudo reboot                                # Test automatic connection"
    echo "  3. $0 test                                    # Verify cellular works"
    echo "  4. $0 wifi 'SSID' 'PASSWORD'                 # Optional: Add WiFi backup"
    echo
    echo "Remote deployment workflow (no WiFi):"
    echo "  1. sudo $0 configure                          # Once during setup"
    echo "  2. sudo reboot                                # System ready with cellular only"
    echo
    echo "Network Priority (after configuration):"
    echo "  • Cellular (wwan0): Primary internet (metric 50, priority 100)"
    echo "  • WiFi (wlan0): Backup internet only (metric 300, priority 50)"
    echo "  • end0: Modbus network only (10.250.250.x)"
    echo "  • end1: Modbus network only (192.168.1.x)"
    echo
    echo "System designed to work reliably with cellular only"
    echo "WiFi is optional backup and will not interfere with cellular operation"
    exit 1
fi