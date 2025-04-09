#!/bin/bash
# configure_application.sh - Run application configuration scripts

APP_DIR="/root/raptor"

echo "Running application configuration scripts..."

# Activate virtual environment
source "$APP_DIR/venv/bin/activate"

# Run cloud registration script
python "$APP_DIR/src/jobs/configuration/py" -c 

# Check the exit code of the Python script
if [ $? -ne 0 ]; then
    echo "ERROR: Commissioing script failed"
    exit 1
fi

# Run hardware configuration script
python "$APP_DIR/src/jobs/configuration/py" -n 
# Check the exit code of the Python script
if [ $? -ne 0 ]; then
    echo "ERROR: Configuration script failed"
    exit 1
fi

echo "Application configuration complete."
exit 0
