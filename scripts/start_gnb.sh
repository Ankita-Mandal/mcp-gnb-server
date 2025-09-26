#!/bin/bash

# Script to start the gNB server on host
# This version uses the existing MCP container with proper host access

echo "Starting gNB server on host..."

# Get the MCP container name/ID
CONTAINER_NAME="gnb-new"

# Check if container exists and is running
if ! docker ps --format "table {{.Names}}" | grep -q "$CONTAINER_NAME"; then
    echo "ERROR: MCP container '$CONTAINER_NAME' is not running"
    echo "Please start the MCP server first with: docker-compose up -d"
    exit 1
fi

echo "Using MCP container: $CONTAINER_NAME"

# Execute the start logic inside the existing MCP container
docker exec "$CONTAINER_NAME" sh -c "
    # Host paths (these are the actual host paths, not container paths)
    HOST_BUILD_DIR='/home/xmili/Documents/Abhiram/USRPworkarea/oai-setup/openairinterface5g/cmake_targets/ran_build/build'
    HOST_CONFIG_PATH='/home/xmili/Documents/Abhiram/USRPworkarea/oai-setup/openairinterface5g/ci-scripts/conf_files/gnb.sa.band78.51prb.usrpb200.conf'
    GNB_EXECUTABLE='./nr-softmodem'
    GAIN_VALUE='3'
    USRP_TX_THREAD_CONFIG='1'
    
    echo 'Checking for existing gNB processes on host...'
    
    # Check for running processes using the host PID namespace
    # Since container has pid: host, this should see host processes
    gnb_pids=\$(pgrep -f 'nr-softmodem' 2>/dev/null || true)
    
    if [ -n \"\$gnb_pids\" ]; then
        echo 'Found gNB process PIDs: '\$gnb_pids
        echo 'Checking if these are actual running processes...'
        
        active_pids=''
        for pid in \$gnb_pids; do
            if [ -f \"/proc/\$pid/status\" ]; then
                status=\$(grep '^State:' \"/proc/\$pid/status\" 2>/dev/null | awk '{print \$2}' || echo 'unknown')
                echo \"PID \$pid status: \$status\"
                if [ \"\$status\" != \"Z\" ] && [ \"\$status\" != \"unknown\" ]; then
                    active_pids=\"\$active_pids \$pid\"
                fi
            else
                echo \"PID \$pid does not exist in /proc (stale reference)\"
            fi
        done
        
        if [ -n \"\$active_pids\" ]; then
            echo 'Found active gNB processes with PIDs:'\$active_pids
            echo 'Stop existing gNB first using stop_gnb tool.'
            exit 1
        else
            echo 'All found PIDs are zombie/stale processes, proceeding with start...'
        fi
    fi
    
    echo 'No active gNB processes found. Starting new gNB on host...'
    
    # Use nsenter to execute on the actual host (more reliable than pid: host)
    nsenter -t 1 -m -p sh -c \"
        # Change to build directory on host
        cd '\$HOST_BUILD_DIR' || {
            echo 'ERROR: Cannot change to build directory: '\$HOST_BUILD_DIR
            exit 1
        }
        
        # Generate log filename with timestamp
        log_file='gnb_\$(date +%F_%H%M%S).log'
        
        # Build the command
        cmd='sudo \$GNB_EXECUTABLE -O \'\$HOST_CONFIG_PATH\' -g \$GAIN_VALUE --usrp-tx-thread-config \$USRP_TX_THREAD_CONFIG'
        
        echo 'Executing on host: '\$cmd
        echo 'Log file: '\$HOST_BUILD_DIR'/'\$log_file
        
        # Start gNB in background
        nohup sh -c '\$cmd' > '\$log_file' 2>&1 &
        
        # Give it time to start
        sleep 3
        
        # Check if it started successfully
        gnb_pids=\$(pgrep -f 'nr-softmodem' 2>/dev/null || true)
        if [ -n '\$gnb_pids' ]; then
            echo 'gNB started successfully on host with PID(s): '\$gnb_pids
            exit 0
        else
            echo 'Failed to start gNB on host. Check log file: '\$HOST_BUILD_DIR'/'\$log_file
            exit 1
        fi
    \"
"
