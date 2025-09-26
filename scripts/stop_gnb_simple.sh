#!/bin/bash

# Script to stop the currently running gNB server
# This version works when container uses pid: "host" in docker-compose.yml

echo "Stopping gNB server..."

# Check if gNB process is running
gnb_pids=$(pgrep -f "nr-softmodem" 2>/dev/null || true)

if [ -z "$gnb_pids" ]; then
    echo "No gNB process found running."
    exit 0
fi

echo "Found gNB process(es): $gnb_pids"

# Stop the gNB process
sudo pkill -TERM -f "nr-softmodem"

if [ $? -eq 0 ]; then
    echo "gNB process stopped successfully."
    exit 0
else
    echo "Failed to stop gNB process."
    exit 1
fi
