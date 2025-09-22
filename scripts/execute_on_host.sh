#!/bin/bash

# execute_on_host.sh
# Simple wrapper to execute gNB restart on host from container

set -e

# Host paths and environment
export GNB_BUILD_DIR="/home/xmili/Documents/Abhiram/USRPworkarea/oai-setup/openairinterface5g/cmake_targets/ran_build/build"
export GNB_CONFIG_FILE="gnb.sa.band78.51prb.usrpb200.conf"
export GNB_EXECUTABLE="./nr-softmodem"
export GAIN_VALUE="3"
export USRP_TX_THREAD_CONFIG="1"
export RESTART_TIMEOUT="30"

# Log function
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [HOST-EXEC] $1"
}

log_message "=== Host gNB Execution Started ==="

# Change to build directory
cd "$GNB_BUILD_DIR" || {
    log_message "ERROR: Cannot change to build directory: $GNB_BUILD_DIR"
    exit 1
}

# Stop existing gNB processes
log_message "Stopping existing gNB processes..."
pids=$(pgrep -f "nr-softmodem" 2>/dev/null || true)
if [[ -n "$pids" ]]; then
    log_message "Found existing gNB processes: $pids"
    echo "$pids" | xargs -r kill -TERM 2>/dev/null || true
    sleep 3
    remaining=$(pgrep -f "nr-softmodem" 2>/dev/null || true)
    if [[ -n "$remaining" ]]; then
        echo "$remaining" | xargs -r kill -KILL 2>/dev/null || true
    fi
    log_message "Existing processes stopped"
else
    log_message "No existing gNB processes found"
fi

# Start gNB
log_message "Starting gNB..."
config_path="/home/xmili/Documents/Abhiram/USRPworkarea/oai-setup/openairinterface5g/ci-scripts/conf_files/$GNB_CONFIG_FILE"
log_file="gnb_$(date +%F_%H%M%S).log"

cmd="sudo $GNB_EXECUTABLE -O $config_path -g $GAIN_VALUE --usrp-tx-thread-config $USRP_TX_THREAD_CONFIG"
log_message "Executing: $cmd"
log_message "Log file: $GNB_BUILD_DIR/$log_file"

# Start in background
nohup bash -c "$cmd" > "$log_file" 2>&1 &
gnb_pid=$!

log_message "gNB started with PID: $gnb_pid"

# Check if it started successfully
sleep 3
if kill -0 "$gnb_pid" 2>/dev/null; then
    log_message "SUCCESS: gNB is running on host"
    echo "gNB successfully started on host with PID $gnb_pid"
else
    log_message "ERROR: gNB failed to start on host"
    log_message "Check log file: $GNB_BUILD_DIR/$log_file"
    exit 1
fi

log_message "=== Host gNB Execution Completed ==="
