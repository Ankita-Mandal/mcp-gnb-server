#!/bin/bash

# Script to start the gNB server with proper library paths
# Uses mounted OAI directory and libraries

echo "Starting gNB server..."

# Container paths (mounted from host via docker-compose.yml)
CONTAINER_BUILD_DIR="/app/gnb-logs"
CONTAINER_CONFIG_PATH="/app/oai-files/gnb.sa.band78.51prb.usrpb200.conf"

# OAI paths in container (mounted from host)
OAI_DIR="/app/oai-root"
OAI_BUILD_DIR="$OAI_DIR/cmake_targets/ran_build/build"
GNB_EXECUTABLE="./nr-softmodem"
GAIN_VALUE="3"
USRP_TX_THREAD_CONFIG="1"

# echo "Checking for existing gNB processes..."

# # Check for running processes
# gnb_pids=$(pgrep -f "nr-softmodem" 2>/dev/null || true)

# if [ -n "$gnb_pids" ]; then
#     echo "Found gNB process PIDs: $gnb_pids"
#     echo "Checking if these are actual running processes..."
    
#     active_pids=""
#     for pid in $gnb_pids; do
#         if [ -f "/proc/$pid/status" ]; then
#             status=$(grep '^State:' "/proc/$pid/status" 2>/dev/null | awk '{print $2}' || echo 'unknown')
#             echo "PID $pid status: $status"
#             if [ "$status" != "Z" ] && [ "$status" != "unknown" ]; then
#                 active_pids="$active_pids $pid"
#             fi
#         else
#             echo "PID $pid does not exist in /proc (stale reference)"
#         fi
#     done
    
#     if [ -n "$active_pids" ]; then
#         echo "Found active gNB processes with PIDs:$active_pids"
#         echo "Stop existing gNB first using stop_gnb tool."
#         exit 1
#     else
#         echo "All found PIDs are zombie/stale processes, proceeding with start..."
#     fi
# fi

# echo "No active gNB processes found. Starting new gNB..."

# Verify OAI directories exist
if [ ! -d "$OAI_BUILD_DIR" ]; then
    echo "ERROR: OAI build directory not found: $OAI_BUILD_DIR"
    exit 1
fi

if [ ! -f "$CONTAINER_CONFIG_PATH" ]; then
    echo "ERROR: Config file not found: $CONTAINER_CONFIG_PATH"
    exit 1
fi

# Generate log filename with timestamp
log_file="gnb_$(date +%F_%H%M%S).log"
log_path="$CONTAINER_BUILD_DIR/$log_file"

# Set library paths
export LD_LIBRARY_PATH="$OAI_BUILD_DIR:$OAI_DIR/openair2/COMMON:$OAI_DIR/lib:$LD_LIBRARY_PATH"

echo "Using LD_LIBRARY_PATH: $LD_LIBRARY_PATH"
echo "Starting gNB from: $OAI_BUILD_DIR"
echo "Using config: $CONTAINER_CONFIG_PATH"
echo "Log file: $log_path"

# Change to build directory
cd "$OAI_BUILD_DIR" || {
    echo "ERROR: Cannot change to build directory: $OAI_BUILD_DIR"
    exit 1
}

# Build the command using HOST paths (where libraries exist)
HOST_BUILD_DIR="/home/xmili/Documents/Abhiram/USRPworkarea/oai-setup/openairinterface5g/cmake_targets/ran_build/build"
HOST_CONFIG_PATH="/home/xmili/Documents/Abhiram/USRPworkarea/oai-setup/openairinterface5g/ci-scripts/conf_files/gnb.sa.band78.51prb.usrpb200.conf"
cmd="cd '$HOST_BUILD_DIR' && sudo $GNB_EXECUTABLE -O '$HOST_CONFIG_PATH' -g $GAIN_VALUE --usrp-tx-thread-config $USRP_TX_THREAD_CONFIG"

echo "Executing on host: $cmd"
echo "Log file: $log_path"

# Use nsenter to execute on the actual host (PID 1 namespace)
#nsenter -t 1 -m -p bash -c "$cmd" > "/tmp/gnb_tmp.log" 2>&1 &
nsenter -t 1 -m -p bash -c "$cmd" > "$log_path" 2>&1 &
# Give it time to start
sleep 5

# Copy log from tmp to mounted volume
# cp "/tmp/gnb_tmp.log" "$log_path" 2>/dev/null || true

# Give it time to start
sleep 5

# Check if it started successfully
gnb_pids=$(pgrep -f "nr-softmodem" 2>/dev/null || true)
if [ -n "$gnb_pids" ]; then
    echo "gNB started successfully with PID(s): $gnb_pids. Check log file: $log_path"
    exit 0
else
    echo "Failed to start gNB. Check log file: $log_path"
    exit 1
fi