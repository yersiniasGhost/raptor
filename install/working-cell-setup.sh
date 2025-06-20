#!/bin/bash
# TS-7180 Nimbelink Skywire LTE CAT4 Modem Setup Script

# Exit on error
set -e

# Log function for better visibility
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Your APN
APN="iot.aer.net"
# For TS-7180, we're using the UART interface
MODEM_DEV="/dev/ttymxc2"
log "Using modem device: $MODEM_DEV with APN: $APN"

# Power on sequence for the Nimbelink modem on TS-7180
log "Powering up and initializing the modem..."


# Power up the modem with 4V (as per documentation for cell modems)
log "Powering up the modem with 4V..."
gpioset 5 17=1
sleep 20

# Enable USB if needed
log "Enabling USB for the modem..."
gpioset 2 12=0
sleep 20

# Toggle the power button signal (required for most Nimbelink modems)
log "Toggling power button signal..."
gpioset 2 19=1
sleep 5
gpioset 2 19=0
sleep 60  # Give the modem time to boot up

# Configure UART for the modem
log "Configuring UART for the modem..."
tshwctl --addr 307 --poke 1 # Claim bluetooth UART3 (ttymxc2) for modem

# Configure serial port
log "Configuring serial port..."
#stty -F $MODEM_DEV 115200 raw -echo -onlcr
#stty -F $MODEM_DEV 115200 -echo -onlcr
stty -F $MODEM_DEV 115200 cs8 -parenb -cstopb -echo -onlcr


# Function to send AT command and get response
send_at_command() {
    local command=$1
    local timeout=${2:-3}
    local temp_file=$(mktemp)

    # Flush any pending data
    dd if=$MODEM_DEV iflag=nonblock of=/dev/null 2>/dev/null || true

    # Start background process to capture output
    (cat $MODEM_DEV > $temp_file) &
    local cat_pid=$!

    # Give cat a moment to start capturing
    sleep 0.5

    # Send the command with proper line ending
    echo -e "$command\r" > $MODEM_DEV

    # Wait for the specified timeout
    sleep $timeout

    # Kill the cat process
    kill $cat_pid 2>/dev/null || true
    wait $cat_pid 2>/dev/null || true

    # Return the captured output
    cat $temp_file
    rm $temp_file
}

# Test AT commands to verify modem operation
log "Testing AT command interface..."
at_response=$(send_at_command "AT" 3)
if echo "$at_response" | grep -q "OK"; then
    log "AT command interface working"
else
    log "AT command test unsuccessful, troubleshooting needed"
    log "Response: $(echo "$at_response" | xxd -p)"
    exit 1
fi

# Check modem firmware version and information
log "Getting modem information..."
modem_info=$(send_at_command "ATI" 3)
log "Modem info: $(echo "$modem_info" | tr -d '\r\n' | tr '\0' ' ')"

# Check signal strength
log "Checking signal strength..."
csq_response=$(send_at_command "AT+CSQ" 3)
log "CSQ response: $(echo "$csq_response" | tr -d '\r\n' | tr '\0' ' ')"

signal=$(echo "$csq_response" | grep -o "+CSQ: [0-9]\+,[0-9]\+" | cut -d" " -f2 | cut -d"," -f1)
if [ -n "$signal" ]; then
    if [ "$signal" -ge 10 ]; then
        log "Signal strength is good: $signal"
    else
        log "Warning: Signal strength is weak: $signal"
    fi
else
    log "Warning: Could not determine signal strength"
fi

# Check if modem is registered on the network
log "Checking network registration..."
cereg_response=$(send_at_command "AT+CEREG?" 3)
log "CEREG response: $(echo "$cereg_response" | tr -d '\r\n' | tr '\0' ' ')"

log "Script completed"
exit 0
