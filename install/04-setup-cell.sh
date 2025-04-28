#!/bin/bash
# TS-7180 Nimbelink Cellular Modem Setup and Test Script
# This script configures and tests a Nimbelink cellular modem connection

# Exit on error
set -e

# Log function for better visibility
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Error handling function
handle_error() {
    log "ERROR: $1"
    exit 1
}

if ! lsusb | grep -iE "huawei|sierra|quectel|telit|ublox|simcom" > /dev/null; then
        handle_error "No cellular modem detected. Please check hardware connection."
fi

MODEM_DEV="/dev/ttyUSB2"
log "Using modem device: $MODEM_DEV"

# Create chat script for establishing PPP connection
log "Creating chat script..."
cat > /etc/chatscripts/cellular-chat << EOF
ABORT 'BUSY'
ABORT 'NO CARRIER'
ABORT 'ERROR'
'' 'ATZ'
OK 'AT+CGDCONT=1,"IP","$APN"'
OK 'ATD*99#'
CONNECT ''
EOF

# Create PPP options file
log "Creating PPP options file..."
cat > /etc/ppp/peers/cellular << EOF
connect "/usr/sbin/chat -v -f /etc/chatscripts/cellular-chat"
$MODEM_DEV
115200
noauth
defaultroute
usepeerdns
nocrtscts
debug
ipcp-accept-local
ipcp-accept-remote
novj
novjccomp
EOF

APN="nxtgenphone"
log "Using APN: $APN"


# Based on common configurations for multi-interface modems:
# - ttyUSB0: Usually for AT commands
# - ttyUSB1: Often used for PPP data connection
# - Other interfaces: Various control and diagnostic functions

# Test for AT command interface
AT_INTERFACE=""
for dev in /dev/ttyUSB0 /dev/ttyUSB2; do
    log "Testing $dev for AT commands..."
    stty -F "$dev" 115200 raw -echo
    echo -e "AT\r" > "$dev"
    sleep 2
    response=$(cat < "$dev" 2>/dev/null || echo "")

    if echo "$response" | grep -q "OK"; then
        log "✓ Found AT command interface: $dev"
        AT_INTERFACE="$dev"
        break
    else
        log "✗ $dev is not the AT command interface"
    fi
done




# Test AT commands to verify modem operation
log "Testing AT command interface..."
echo -e "AT\r" > $MODEM_DEV
sleep 1
if grep -q "OK" < $MODEM_DEV; then
    log "AT command interface working"
else
    log "Warning: AT command test unsuccessful, but continuing..."
fi

# Check signal strength
log "Checking signal strength..."
echo -e "AT+CSQ\r" > $MODEM_DEV
sleep 1
signal=$(cat < $MODEM_DEV | grep "+CSQ:" | cut -d":" -f2 | tr -d "," | awk '{print $1}')
if [ -n "$signal" ]; then
    if [ "$signal" -ge 10 ]; then
        log "Signal strength is good: $signal"
    else
        log "Warning: Signal strength is weak: $signal"
    fi
else
    log "Warning: Could not determine signal strength"
fi



