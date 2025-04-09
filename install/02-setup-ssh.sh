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
exit 0
