#!/bin/bash
# master_install.sh - Master script for TS-7180 IIoT device setup

set -e  # Exit on any error

# Define colors for better readability
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Define script directory
SCRIPTS_DIR="$(dirname "$(readlink -f "$0")")"
CONFIG_FILE="${1:-./device_config.conf}"
APP_DIR="/root/raptor"
GITHUB_REPO="git@github.com:YersiniasGhost/raptor.git"

# Log function for consistent output
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
    error "This script must be run as root"
fi

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    error "Configuration file not found: $CONFIG_FILE"
fi

# Source the configuration file
log "Loading configuration from: $CONFIG_FILE"
source "$CONFIG_FILE"

# Validate configuration
if [ -z "$GITHUB_REPO" ]; then
    error "GITHUB_REPO not defined in configuration file"
fi


# Display welcome message
log "Starting TS-7180 IIoT device setup..."
log "This script will set up all components for your IIoT application"

# Function to run a script and check its exit status
run_script() {
    script="$1"
    shift
    log "Running $script..."
    
    if [ ! -f "$SCRIPTS_DIR/$script" ]; then
        error "Script not found: $SCRIPTS_DIR/$script"
    fi
    
    chmod +x "$SCRIPTS_DIR/$script"
    "$SCRIPTS_DIR/$script" "$@"
    
    if [ $? -ne 0 ]; then
        error "Script failed: $script"
    fi
    
    log "Successfully completed: $script"
}
# 1. Setup connectivity (Wi-Fi or Cellular)
log "Step 1: Setting up network connectivity"

NETWORK_CONFIGURED=false

if [ "$WIFI" = "True" ]; then
    if [ -z "$SSID" ] || [ -z "$SSID_PASS" ]; then
        warning "Wi-Fi enabled but credentials missing. Skipping Wi-Fi setup."
    else
        log "Setting up Wi-Fi connection"
        run_script "01-setup-wifi.sh" "$SSID" "$SSID_PASS"
        NETWORK_CONFIGURED=true
    fi
fi

if [ "$CELL" = "True" ] && [ "$NETWORK_CONFIGURED" = false ]; then
    if [ -z "$CELL_APN" ]; then
        warning "Cellular enabled but APN missing. Skipping cellular setup."
    else
        log "Setting up cellular connection"
        run_script "01-setup-cellular.sh" "$CELL_APN"
        NETWORK_CONFIGURED=true
    fi
fi

if [ "$NETWORK_CONFIGURED" = false ]; then
    warning "No network configured. Using existing network configuration."
    # Basic network check
    if ! ping -c 1 -W 5 8.8.8.8 &>/dev/null; then
        error "No network connectivity detected. Cannot proceed with installation."
    fi
    log "Network connectivity confirmed"
fi



# 2. Setup SSH
log "Step 2: Configuring SSH"
run_script "02-setup-ssh.sh" "$CONFIG_FILE"

# 3. Install system dependencies
log "Step 3: Installing system dependencies"
run_script "03-system-dep.sh"

# 4. Setup GitHub and clone repository
log "Step 4: Setting up GitHub repository"
run_script "04-github.sh" "$GITHUB_REPO" "$APP_DIR"

# 5. Create secret .env
log "Step 5: Creating .env"
run_script "05-exports.sh"

# 6. Configure and commission the application
log "Step 6: Configuring application"
run_script "06-configure.sh" "$APP_DIR"

# 7. Setup system services
log "Step 7: Setting up system services"
run_script "07-services.sh" "$APP_DIR"

# Final status
log "Installation complete! Your TS-7180 has been configured successfully."
log "Services status:"
systemctl status vmc-ui.service --no-pager
systemctl status iot-controller.service --no-pager

# Print system information
log "System information:"
hostname -I
df -h
free -m

log "Thank you for using the TS-7180 IIoT setup script."
exit 0
