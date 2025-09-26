#!/bin/bash

# Script to stop the currently running gNB server using docker exec

echo "Stopping gNB server..."

# Try to execute command on host using docker exec
# We'll use a trick: run a temporary container that shares the host PID namespace
docker run --rm --pid=host --privileged alpine:latest sh -c "
    # Check if gNB process is running
    gnb_pids=\$(pgrep -f 'nr-softmodem' 2>/dev/null || true)
    
    if [ -z \"\$gnb_pids\" ]; then
        echo 'No gNB process found running.'
        exit 0
    fi
    
    echo 'Found gNB process(es): '\$gnb_pids
    
    # Stop the gNB process
    pkill -TERM -f 'nr-softmodem'
    
    if [ \$? -eq 0 ]; then
        echo 'gNB process stopped successfully.'
        exit 0
    else
        echo 'Failed to stop gNB process.'
        exit 1
    fi
"
