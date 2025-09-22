#!/bin/bash

# restart_gnb.sh
# Restarts the gNB after configuration modifications
# This script stops any existing gNB process and starts it with the updated configuration
# All configuration comes from environment variables set by Docker Compose or host environment

set -e  # Exit on any error

# Validate required environment variables
required_vars=("GNB_BUILD_DIR" "GNB_CONFIG_FILE" "GNB_EXECUTABLE" "GAIN_VALUE")
for var in "${required_vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        echo "ERROR: Required environment variable $var is not set"
        exit 1
    fi
done

# Configuration from environment variables only
USRP_TX_THREAD_CONFIG="${USRP_TX_THREAD_CONFIG:-1}"
RESTART_TIMEOUT="${RESTART_TIMEOUT:-30}"  # seconds to wait for graceful shutdown

# Function to log messages with timestamp
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to find and kill existing gNB processes
# stop_existing_gnb() {
#     log_message "Checking for existing gNB processes..."
    
#     # Find processes containing nr-softmodem
#     local pids=$(pgrep -f "nr-softmodem" 2>/dev/null || true)
    
#     if [[ -n "$pids" ]]; then
#         log_message "Found existing gNB processes: $pids"
        
#         # Try graceful shutdown first (SIGTERM)
#         log_message "Attempting graceful shutdown..."
#         echo "$pids" | xargs -r kill -TERM 2>/dev/null || true
#         sleep 2
#         # Wait for graceful shutdown with detailed verification
#         log_message "Waiting for processes to terminate gracefully (timeout: ${RESTART_TIMEOUT}s)..."
#         local count=0
#         while [[ $count -lt $RESTART_TIMEOUT ]]; do
#             local remaining_pids=$(pgrep -f "nr-softmodem" 2>/dev/null || true)
#             if [[ -z "$remaining_pids" ]]; then
#                 log_message "All gNB processes stopped gracefully"
#                 break
#             fi
#             log_message "Still waiting for processes: $remaining_pids (${count}/${RESTART_TIMEOUT}s)"
#             sleep 1
#             ((count++))
#         done
        
#         # Final check and force kill if still running
#         local final_pids=$(pgrep -f "nr-softmodem" 2>/dev/null || true)
#         if [[ -n "$final_pids" ]]; then
#             log_message "Force killing remaining gNB processes: $final_pids"
#             echo "$final_pids" | xargs -r kill -KILL 2>/dev/null || true
            
#             # Wait additional time after force kill
#             log_message "Waiting for force-killed processes to fully terminate..."
#             sleep 3
            
#             # Verify complete termination
#             local verify_pids=$(pgrep -f "nr-softmodem" 2>/dev/null || true)
#             if [[ -n "$verify_pids" ]]; then
#                 log_message "ERROR: Failed to stop gNB processes: $verify_pids"
#                 log_message "Cannot proceed with restart - processes still running"
#                 exit 1
#             fi
#         fi
        
#         # Final verification that NO processes remain
#         local final_check=$(pgrep -f "nr-softmodem" 2>/dev/null || true)
#         if [[ -n "$final_check" ]]; then
#             log_message "ERROR: gNB processes still detected after termination: $final_check"
#             exit 1
#         fi
        
#         log_message " All gNB processes successfully terminated"
#     else
#         log_message "No existing gNB processes found"
#     fi
    
#     # Additional safety delay to ensure system cleanup
#     log_message "Waiting for system cleanup..."
#     sleep 2
# }

# Function to find and kill existing gNB processes
stop_existing_gnb() {
    log_message "Stopping existing gNB processes..."
    
    # Find and kill all nr-softmodem processes
    local pids=$(pgrep -f "nr-softmodem" 2>/dev/null || true)
    
    if [[ -n "$pids" ]]; then
        log_message "Found gNB processes: $pids"
        log_message "Killing processes..."
        echo "$pids" | xargs -r kill -TERM 2>/dev/null || true  # Graceful first
        sleep 3
        remaining=$(pgrep -f "nr-softmodem" 2>/dev/null || true)
        if [[ -n "$remaining" ]]; then
            echo "$remaining" | xargs -r kill -KILL 2>/dev/null || true  # Force if needed
        sleep 1
        fi
        log_message "gNB processes stopped"
    else
        log_message "No existing gNB processes found"
    fi
}


# Function to validate configuration file
validate_config() {
    local config_path="/app/oai-files/$GNB_CONFIG_FILE"
    
    if [[ ! -f "$config_path" ]]; then
        log_message "ERROR: Configuration file not found: $config_path"
        exit 1
    fi
    
    log_message "Configuration file validated: $config_path"
}

# Function to validate executable
validate_executable() {
    local exec_path="$GNB_BUILD_DIR/$GNB_EXECUTABLE"
    
    if [[ ! -f "$exec_path" ]]; then
        log_message "ERROR: gNB executable not found: $exec_path"
        exit 1
    fi
    
    if [[ ! -x "$exec_path" ]]; then
        log_message "ERROR: gNB executable is not executable: $exec_path"
        exit 1
    fi
    
    log_message "gNB executable validated: $exec_path"
}

# Function to start gNB
start_gnb() {
    log_message "Starting gNB with updated configuration..."
    
    # CRITICAL: Verify no gNB processes are running before starting
    local running_check=$(pgrep -f "nr-softmodem" 2>/dev/null || true)
    if [[ -n "$running_check" ]]; then
        log_message "ERROR: gNB processes still running before start: $running_check"
        log_message "Cannot start new gNB while old processes are active"
        exit 1
    fi
    log_message "Verified no existing gNB processes - safe to start"
    

    # Change to the build directory
    cd "$GNB_BUILD_DIR" || {
        log_message "ERROR: Cannot change to build directory: $GNB_BUILD_DIR"
        exit 1
    }
    
    # Generate log filename with timestamp
    local log_file="gnb_$(date +%F_%H%M%S).log"
    
    # Build the command using mounted config file path
    local cmd="sudo $GNB_EXECUTABLE -O /app/oai-files/$GNB_CONFIG_FILE -g $GAIN_VALUE --usrp-tx-thread-config $USRP_TX_THREAD_CONFIG"
    
    log_message "Executing command: $cmd"
    log_message "Log file: $GNB_BUILD_DIR/$log_file"
    
    # Start gNB in background and redirect output to log file
    nohup bash -c "$cmd" > "$log_file" 2>&1 &
    local gnb_pid=$!
    
    log_message "gNB started with PID: $gnb_pid"
    log_message "Log file created: $log_file"
    
    # Wait a moment to check if process started successfully
    sleep 3
    
    if kill -0 "$gnb_pid" 2>/dev/null; then
        log_message "gNB process is running successfully"
        echo "gNB restarted successfully with PID $gnb_pid, logging to $log_file"
        return 0
    else
        log_message "ERROR: gNB process failed to start or crashed immediately"
        log_message "Check the log file for details: $GNB_BUILD_DIR/$log_file"
        exit 1
    fi
}

# Function to check system requirements
check_requirements() {
    # Check if running as root or with sudo access
    if [[ $EUID -ne 0 ]] && ! sudo -n true 2>/dev/null; then
        log_message "ERROR: This script requires sudo access to run the gNB"
        exit 1
    fi
    
    # Check if build directory exists
    if [[ ! -d "$GNB_BUILD_DIR" ]]; then
        log_message "ERROR: Build directory not found: $GNB_BUILD_DIR"
        exit 1
    fi
}

# Main execution
main() {
    log_message "=== gNB Restart Script Started ==="
    
    # Check system requirements
    check_requirements
    
    # Validate files
    validate_config
    validate_executable
    
    # Stop existing processes
    stop_existing_gnb
    sleep 5
    # Start gNB with new configuration
    start_gnb
    
    log_message "=== gNB Restart Script Completed Successfully ==="
}

# Handle script interruption
trap 'log_message "Script interrupted"; exit 130' INT TERM

# Run main function
main "$@"
