#!/bin/bash
# install_dependencies.sh - Install required system packages

echo "Installing system dependencies..."

# Update package lists
apt-get update

# Install required packages
apt-get install -y git python3 python3-pip python3-dev build-essential \
    libssl-dev libffi-dev python3-setuptools python3-venv pkg-config \
    i2c-tools udev net-tools libsqlite3-dev

echo "System dependencies installed."

