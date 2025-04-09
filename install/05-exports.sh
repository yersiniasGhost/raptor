#!/bin/bash
# set_env_vars.sh - Script to set environment variables

# Create or overwrite the environment variables file
cat > /root/raptor/.env << EOF
DB_PATH=/root/raptor/sqlite/configuration.db
DB_NAME=vmc
DB_USER=root
DB_PASSWORD=NA
API_URL=http://192.169.1.25:3000
SCHEMA_PATH=/root/raptor/src/database/schema.sql
LOG_PATH=/var/log/raptor
# Add any other environment variables here
EOF
