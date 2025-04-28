#!/bin/bash
# setup_ssh.sh - Configure SSH server

echo "Configuring SSH server..."
if grep -q "^PermitRootLogin yes" /etc/ssh/sshd_config; then
    echo "SSH root login is already enabled. No changes needed."
else

    # Enable root login
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

    # Restart SSH service
    systemctl restart ssh
    
    # Create directory for SSH keys
    mkdir -p /root/.ssh
    chmod 700 /root/.ssh
fi

# Get current IP address
CURRENT_IP=$(hostname -I | awk '{print $1}')


# Show SSH key copy instructions
echo "=============================================="
echo "To copy your SSH key to this device, run:"
echo "ssh-copy-id -i ~/.ssh/id_ed25519 root@${CURRENT_IP}"
echo ""
echo "Current IP address of this device: ${CURRENT_IP}"
echo "=============================================="

echo "SSH server configured."
SSH_DIR=/root/.ssh

# Check if configuration file exists
if [ -z "$1" ]; then
    echo "ERROR: Configuration file not specified.  Skipping SSH key setup (github)"
    echo "Usage: $0 <config_file>"
    exit 1
fi

CONFIG_FILE="$1"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Source the configuration file
echo "Loading configuration from: $CONFIG_FILE"
source "$CONFIG_FILE"

# Check if SSH keys are provided in the config file
if [ -z "$SSH_PRIVATE_KEY" ] || [ -z "$SSH_PUBLIC_KEY" ]; then
    echo "ERROR: SSH keys not found in configuration file. Skipping SSH key setup."
    exit 1
fi

# Check if keys already exist
if [ -f "$SSH_DIR/id_ed25519" ] && [ -f "$SSH_DIR/id_ed25519.pub" ]; then
    echo "SSH keys already exist. Checking if they match configuration..."

    # Compare public key
    EXISTING_PUB=$(cat "$SSH_DIR/id_ed25519.pub")
    if [ "$EXISTING_PUB" = "$SSH_PUBLIC_KEY" ]; then
        echo "Existing SSH keys match configuration. No changes needed."
        exit 0
    else
        echo "Existing SSH keys do not match configuration."
        echo "Backing up existing keys..."

        # Backup existing keys
        BACKUP_SUFFIX=$(date +%Y%m%d%H%M%S)
        cp "$SSH_DIR/id_ed25519" "$SSH_DIR/id_ed25519.backup.$BACKUP_SUFFIX"
        cp "$SSH_DIR/id_ed25519.pub" "$SSH_DIR/id_ed25519.pub.backup.$BACKUP_SUFFIX"
    fi
fi

# Write the private key
echo "Installing SSH private key..."
echo "$SSH_PRIVATE_KEY" > "$SSH_DIR/id_ed25519"
chmod 600 "$SSH_DIR/id_ed25519"

# Write the public key
echo "Installing SSH public key..."
echo "$SSH_PUBLIC_KEY" > "$SSH_DIR/id_ed25519.pub"
chmod 644 "$SSH_DIR/id_ed25519.pub"

# Add GitHub to known hosts to avoid prompts
echo "Adding GitHub to known hosts..."
if ! grep -q "github.com" "$SSH_DIR/known_hosts" 2>/dev/null; then
    ssh-keyscan -t rsa github.com >> "$SSH_DIR/known_hosts" 2>/dev/null
fi

# Create SSH config for GitHub if it doesn't exist
if [ ! -f "$SSH_DIR/config" ]; then
    echo "Creating SSH config..."
    cat > "$SSH_DIR/config" << EOF
Host github.com
    HostName github.com
    User git
    IdentityFile $SSH_DIR/id_ed25519
    IdentitiesOnly yes
EOF
    chmod 600 "$SSH_DIR/config"
fi

echo "SSH keys installed successfully"
exit 0
