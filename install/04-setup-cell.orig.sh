#!/bin/bash
# Minimal Cellular Setup for TS-7180
# Phase 1: One-time configuration
# Phase 2: Hardware initialization only (NetworkManager handles the rest)

if [ "$1" = "configure" ]; then
    echo "=== One-Time Cellular Configuration ==="

    if [ "$EUID" -ne 0 ]; then
        echo "Please run as root: sudo $0 configure"
        exit 1
    fi

    echo "Step 1: Installing packages..."
    apt update -qq
    apt install -y libmbim-utils network-manager

    echo "Step 2: Hardware setup and modem configuration..."
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

    echo "Step 3: Creating NetworkManager connection..."
    systemctl start NetworkManager ModemManager
    sleep 10

    # Wait for modem detection
    for i in {1..30}; do
        if mmcli -L 2>/dev/null | grep -q Modem; then break; fi
        sleep 2
    done

    # Create auto-connect cellular connection
    nmcli connection delete cellular 2>/dev/null || true
    nmcli connection add type gsm con-name cellular apn iot.aer.net
    nmcli connection modify cellular connection.autoconnect yes
    nmcli connection modify cellular connection.autoconnect-priority -10

    echo "Step 4: Creating minimal hardware init service..."

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
    echo "   • Cellular hardware init service: enabled"
    echo "   • NetworkManager cellular connection: configured with autoconnect"
    echo "   • Reboot to test: sudo reboot"

elif [ "$1" = "test" ]; then
    echo "=== Testing Current Cellular Status ==="

    echo "Hardware status:"
    echo "  USB modem: $(lsusb | grep -i telit >/dev/null && echo 'detected' || echo 'not found')"
    echo "  MBIM device: $([ -c /dev/cdc-wdm0 ] && echo 'available' || echo 'not available')"
    echo "  wwan0 interface: $(ip link show wwan0 >/dev/null 2>&1 && echo 'exists' || echo 'missing')"

    echo "Service status:"
    echo "  cellular-init: $(systemctl is-active cellular-init 2>/dev/null || echo 'inactive')"
    echo "  NetworkManager: $(systemctl is-active NetworkManager 2>/dev/null || echo 'inactive')"
    echo "  ModemManager: $(systemctl is-active ModemManager 2>/dev/null || echo 'inactive')"

    echo "Connection status:"
    if nmcli connection show cellular >/dev/null 2>&1; then
        echo "  cellular connection: configured"
        echo "  autoconnect: $(nmcli connection show cellular | grep autoconnect: | awk '{print $2}')"
        echo "  active: $(nmcli connection show --active | grep -q cellular && echo 'yes' || echo 'no')"
    else
        echo "  cellular connection: not configured"
    fi

    if ip addr show wwan0 2>/dev/null | grep -q "inet "; then
        IP=$(ip addr show wwan0 | grep "inet " | awk '{print $2}' | head -1)
        echo "  IP address: $IP"
        echo "✅ Cellular connection active"
    else
        echo "  IP address: none"
        echo "❌ Cellular connection not active"
    fi

elif [ "$1" = "connect" ]; then
    echo "=== Manually Activating Cellular Connection ==="
    sudo nmcli connection up cellular

elif [ "$1" = "disconnect" ]; then
    echo "=== Disconnecting Cellular Connection ==="
    sudo nmcli connection down cellular

elif [ "$1" = "logs" ]; then
    echo "=== Cellular Service Logs ==="
    echo "Hardware init logs:"
    journalctl -u cellular-init --no-pager -n 20
    echo
    echo "NetworkManager logs:"
    journalctl -u NetworkManager --no-pager -n 10 | grep -i cellular

else
    echo "TS-7180 Minimal Cellular Setup"
    echo "=============================="
    echo
    echo "Usage:"
    echo "  $0 configure    # One-time setup (run as root)"
    echo "  $0 test         # Check current status"
    echo "  $0 connect      # Manually connect"
    echo "  $0 disconnect   # Manually disconnect"
    echo "  $0 logs         # View service logs"
    echo
    echo "Normal workflow:"
    echo "  1. sudo $0 configure    # Once during setup"
    echo "  2. sudo reboot          # Test automatic connection"
    echo "  3. $0 test              # Verify it's working"
    echo
    echo "After configuration, cellular should connect automatically on every boot"
    exit 1
fi
