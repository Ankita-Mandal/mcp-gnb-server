from typing import Any
import httpx
from fastmcp import FastMCP, Context
import re
import os
import json
import logging
from pathlib import Path
import subprocess
import asyncio
# Initialize FastMCP server
mcp = FastMCP("gNB Agent")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Set specific loggers to DEBUG level
logging.getLogger('mcp').setLevel(logging.DEBUG)
logging.getLogger('fastmcp').setLevel(logging.DEBUG)

logger = logging.getLogger("mcp_server")
logger.setLevel(logging.DEBUG)

# Determine project and configuration directories
PROJECT_ROOT = Path().resolve()
CONF_DIR = Path(
    os.environ.get(
        'OAI_CONF_DIR',
        str(PROJECT_ROOT / "deps/openairinterface5g/ci-scripts/conf_files")
    )
)
logger.info(f"Using configuration directory: {CONF_DIR}")


@mcp.tool()
async def update_gnb_bandwidth(
    bandwidth: str,
    ctx: Context = None
) -> str:
    """
    Updates bandwidth-related parameters in the gNB .conf configuration file for Band 78.
    
    This tool configures the gNB bandwidth to either 10MHz or 20MHz and automatically
    sets the appropriate carrier bandwidth and BWP parameters according to 3GPP standards.
    You should restart the gNB to apply changes.
    
    Args:
        bandwidth: Bandwidth configuration ("10MHz" or "20MHz")
        
    Returns:
        Confirmation message with updated parameters
    """
    # Define bandwidth configurations for Band 78
    bandwidth_configs = {
        "10MHz": {
            "dl_carrierBandwidth": 24,
            "initialDLBWPlocationAndBandwidth": 6325,
            "ul_carrierBandwidth": 24,
            "initialULBWPlocationAndBandwidth": 6325
        },
        "20MHz": {
            "dl_carrierBandwidth": 51,
            "initialDLBWPlocationAndBandwidth": 13750,
            "ul_carrierBandwidth": 51,
            "initialULBWPlocationAndBandwidth": 13750
        }
    }
    
    # Validate bandwidth parameter
    if bandwidth not in bandwidth_configs:
        raise ValueError(f"Invalid bandwidth '{bandwidth}'. Must be '10MHz' or '20MHz'")
    
    # Use environment variable for config file path, with fallback
    config_file_name = os.environ.get('GNB_CONFIG_FILE', 'gnb.sa.band78.51prb.usrpb200.conf')
    
    # If it's just a filename, combine with CONF_DIR
    if '/' not in config_file_name:
        config_file_path = CONF_DIR / config_file_name
    else:
        config_file_path = Path(config_file_name)
    
    # Check if config file exists
    if not config_file_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file_path}")
    
    # Read the current configuration
    try:
        content = config_file_path.read_text()
    except Exception as e:
        raise IOError(f"Failed to read configuration file: {str(e)}")
    
    # Get the bandwidth configuration
    config = bandwidth_configs[bandwidth]
    
    # Track changes made
    changes_made = []
    
    # Parameters to update (bandwidth-specific only)
    parameters = [
        ("dl_carrierBandwidth", config["dl_carrierBandwidth"]),
        ("ul_carrierBandwidth", config["ul_carrierBandwidth"]),
        ("initialDLBWPlocationAndBandwidth", config["initialDLBWPlocationAndBandwidth"]),
        ("initialULBWPlocationAndBandwidth", config["initialULBWPlocationAndBandwidth"])
    ]
    
    for param_name, param_value in parameters:
        # Capture current value for logging (conf format uses = instead of :)
        current_match = re.search(rf"{param_name}\s*=\s*(-?\d+(?:\.\d+)?)", content)
        current_value = current_match.group(1) if current_match else "not found"
        
        # Replace parameter value using regex for .conf format
        # Pattern matches: parameter_name = value; (with optional whitespace and semicolon)
        pattern = rf"({param_name}\s*=\s*)-?\d+(?:\.\d+)?"
        replacement = rf"\g<1>{param_value}"
        
        new_content, count = re.subn(pattern, replacement, content)
        
        if count > 0:
            content = new_content
            changes_made.append(f"{param_name}: {current_value} → {param_value}")
            if ctx:
                await ctx.info(f"Updated {param_name} from {current_value} to {param_value}")
        else:
            if ctx:
                await ctx.warning(f"Parameter {param_name} not found in config file")
    
    if not changes_made:
        return "No parameters were updated. Configuration file may not contain expected parameters."
    
    # Write updated content back to file
    try:
        config_file_path.write_text(content)
    except Exception as e:
        raise IOError(f"Failed to write updated configuration: {str(e)}")
    
    changes_summary = "; ".join(changes_made)
    if ctx:
        await ctx.info(f"Updated gNB configuration for {bandwidth} bandwidth: {changes_summary}")
    
    return f"Successfully configured gNB for {bandwidth} bandwidth in {config_file_path.name}:\n" + "\n".join(changes_made) + f"\n\nRestart the gNB to apply these changes to the network."

@mcp.tool()
async def get_gnb_config(ctx: Context = None) -> str:
    """
    Retrieves the current gNB configuration by running the get_gnb_config.sh script.
    
    This tool executes the shell script that parses the local gNB configuration file
    and returns detailed configuration information in JSON format including:
    - gNB identity (ID, name, tracking area)
    - PLMN configuration (MCC, MNC)
    - RF configuration (band, frequencies, bandwidth)
    - Power settings (SSB, PDSCH, max UE power)
    - SSB and PRACH configuration
    - Antenna configuration
    
    Returns:
        JSON string containing the complete gNB configuration
    """
    import subprocess
    
    # Use environment variable for script path, with fallback
    script_name = os.environ.get('GNB_CONFIG_SCRIPT', 'get_gnb_config.sh')
    scripts_dir = PROJECT_ROOT / "scripts"
    script_path = scripts_dir / script_name
    
    try:
        # Check if script exists
        if not script_path.exists():
            return f'{{"error": "Configuration script not found at {script_path}"}}'
        
        # Make sure script is executable
        script_path.chmod(0o755)
        
        # Run the script and capture output
        result = subprocess.run(
            [str(script_path)],
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout
        )
        
        if result.returncode == 0:
            # Script executed successfully, return the JSON output
            if ctx:
                await ctx.info(f"Successfully retrieved gNB configuration from {script_path}")
            return result.stdout.strip()
        else:
            # Script failed, return error information
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            return f'{{"error": "Script execution failed with return code {result.returncode}", "stderr": "{error_msg}"}}'
            
    except subprocess.TimeoutExpired:
        return '{"error": "Script execution timed out after 30 seconds"}'
    except subprocess.CalledProcessError as e:
        return f'{{"error": "Script execution failed", "return_code": {e.returncode}, "stderr": "{e.stderr}"}}'
    except Exception as e:
        return f'{{"error": "Unexpected error running configuration script", "details": "{str(e)}"}}'

@mcp.tool()
async def get_gnb_logs(
    lines: int = 100,
    ctx: Context = None
) -> str:
    """
    Retrieves the latest gNB log file content.
    
    This tool finds and reads from the most recent gNB log file in the cmake_targets/ran_build/build directory.
    Log files follow the pattern: gnb_YYYY-MM-DD_HHMMSS.log
    
    Args:
        lines: Number of lines to read from the end of the log file (default: 100, max: 1000)
        
    Returns:
        Content from the latest gNB log file
    """
    import glob
    from datetime import datetime
    
    # Validate lines parameter
    if lines < 1:
        lines = 100
    elif lines > 1000:
        lines = 1000
    
    # Use environment variable for log directory with fallback
    log_base_dir = os.environ.get(
        'GNB_LOG_DIR', 
        '/home/xmili/Documents/Abhiram/USRPworkarea/oai-setup/openairinterface5g/cmake_targets/ran_build/build'
    )
    
    log_dir = Path(log_base_dir)
    
    try:
        # Check if log directory exists
        if not log_dir.exists():
            return f'{{"error": "Log directory not found: {log_dir}"}}'
        
        # Find all gNB log files matching the pattern
        log_pattern = str(log_dir / "gnb_*.log")
        log_files = glob.glob(log_pattern)
        
        if not log_files:
            return f'{{"error": "No gNB log files found in {log_dir}"}}'
        
        # Sort by modification time to get the latest file
        latest_log = max(log_files, key=os.path.getmtime)
        latest_log_path = Path(latest_log)
        
        # Get file info
        file_size = latest_log_path.stat().st_size
        mod_time = datetime.fromtimestamp(latest_log_path.stat().st_mtime)
        
        if ctx:
            await ctx.info(f"Reading latest gNB log: {latest_log_path.name} (size: {file_size} bytes, modified: {mod_time})")
        
        # Read the last N lines from the file
        try:
            with open(latest_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                # For large files, read from the end
                if file_size > 1024 * 1024:  # 1MB
                    # Seek to near the end and read backwards
                    f.seek(max(0, file_size - 50000))  # Read last ~50KB
                    content_lines = f.readlines()
                else:
                    content_lines = f.readlines()
                
                # Get the last N lines
                last_lines = content_lines[-lines:] if len(content_lines) > lines else content_lines
                content = ''.join(last_lines)
        
        except UnicodeDecodeError:
            # Try with different encoding if UTF-8 fails
            with open(latest_log_path, 'r', encoding='latin-1', errors='ignore') as f:
                if file_size > 1024 * 1024:
                    f.seek(max(0, file_size - 50000))
                    content_lines = f.readlines()
                else:
                    content_lines = f.readlines()
                
                last_lines = content_lines[-lines:] if len(content_lines) > lines else content_lines
                content = ''.join(last_lines)
        
        # Build response with metadata
        response = {
            "timestamp": datetime.now().isoformat(),
            "log_file": {
                "path": str(latest_log_path),
                "name": latest_log_path.name,
                "size_bytes": file_size,
                "modified": mod_time.isoformat(),
                "lines_requested": lines,
                "lines_returned": len(last_lines)
            },
            "content": content.strip()
        }
        
        return json.dumps(response, indent=2)
        
    except Exception as e:
        error_msg = f"Error reading gNB log file: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return f'{{"error": "{error_msg}"}}'

# @mcp.tool()
# async def restart_gnb(ctx: Context = None) -> str:
#     """
#     Restarts the gNB in the connected usrp.
    
#     This tool executes a script that stops any existing gNB processes and starts a new one
#     with the current configuration. The gNB will be started in the background with logging.
    
#     Note: This requires sudo access. Ensure the script has appropriate sudo permissions configured.

#     Returns:
#         Status message indicating whether the restart was successful
#     """
#     script_path = Path(__file__).parent / "scripts" / "restart_gnb.sh"
    
#     if not script_path.exists():
#         error_msg = f"Restart script not found: {script_path}"
#         if ctx:
#             await ctx.error(error_msg)
#         return f"Error: {error_msg}"
    
#     # # Make sure the script is executable
#     # script_path.chmod(0o755)
    
#     try:
#         # Execute the restart script with sudo
#         if ctx:
#             await ctx.info("Starting gNB restart process...")
        
#         process = await asyncio.create_subprocess_exec(
#             str(script_path),
#             stdout=asyncio.subprocess.PIPE,
#             stderr=asyncio.subprocess.PIPE
#         )
        
#         stdout, stderr = await process.communicate()
        
#         if process.returncode == 0:
#             output = stdout.decode().strip()
#             if ctx:
#                 await ctx.info(f"gNB restart successful")
            
#             # Extract the success message from the script output
#             lines = output.split('\n')
#             success_line = next((line for line in lines if "gNB restarted successfully" in line), "")
            
#             if success_line:
#                 return success_line
#             else:
#                 return "gNB restarted successfully"
#         else:
#             error = stderr.decode().strip() if stderr else stdout.decode().strip()
#             if ctx:
#                 await ctx.warning(f"gNB restart failed: {error}")
            
#             if process.returncode == 130:
#                 return "gNB restart was interrupted"
#             elif "sudo" in error.lower() and "password" in error.lower():
#                 return "Error: sudo password required. Please configure passwordless sudo for the gNB executable or run the MCP server with appropriate privileges."
#             else:
#                 return f"Failed to restart gNB: {error}"
                
#     except Exception as e:
#         error_msg = f"Error executing restart script: {str(e)}"
#         if ctx:
#             await ctx.error(error_msg)
#         return f"Error restarting gNB: {error_msg}"

@mcp.tool()
async def update_gnb_mcs(
    dl_mcs: int,
    ul_mcs: int,
    ctx: Context = None
) -> str:
    """
    Updates MCS (Modulation and Coding Scheme) parameters in the gNB configuration file.

    This tool configures the downlink and uplink MCS parameters which control
    the modulation and coding schemes used by the gNB. Valid MCS values are 0-28.
    You should restart the gNB to apply changes.

    Args:
        dl_mcs: Downlink MCS value (0-28) used for both min and max MCS
        ul_mcs: Uplink MCS value (0-28) used for both min and max MCS

    Returns:
        Confirmation message with updated parameters or guidance
    """
    # Validate MCS parameter ranges
    if not (0 <= dl_mcs <= 28):
        error_msg = f"Invalid dl_mcs value '{dl_mcs}'. Must be between 0 and 28"
        if ctx:
            await ctx.error(error_msg)
        return f"Error: {error_msg}"
    
    if not (0 <= ul_mcs <= 28):
        error_msg = f"Invalid ul_mcs value '{ul_mcs}'. Must be between 0 and 28"
        if ctx:
            await ctx.error(error_msg)
        return f"Error: {error_msg}"

    # Use environment variables for configuration paths
    conf_dir = os.environ.get('OAI_CONF_DIR', '/app/oai-files')
    config_file = os.environ.get('GNB_CONFIG_FILE', 'gnb.sa.band78.51prb.usrpb200.conf')
    
    target_file = Path(conf_dir) / config_file
    
    if not target_file.exists():
        error_msg = f"Configuration file not found: {target_file}"
        if ctx:
            await ctx.error(error_msg)
        return f"Error: {error_msg}"

    try:
        # Read current configuration
        content = target_file.read_text()
        
        if ctx:
            await ctx.info(f"Updating MCS parameters in {target_file.name}")

        # Track changes made
        changes_made = []

        # Parameters to update (using the same value for min and max)
        parameters = [
            ("dl_min_mcs", dl_mcs),
            ("dl_max_mcs", dl_mcs),
            ("ul_min_mcs", ul_mcs),
            ("ul_max_mcs", ul_mcs)
        ]

        for param_name, param_value in parameters:
            # Capture current value for logging
            current_match = re.search(rf"{param_name}\s*=\s*(\d+)", content)
            current_value = current_match.group(1) if current_match else "not found"

            # Replace parameter value using regex
            new_content, count = re.subn(
                rf"({param_name}\s*=\s*)\d+", 
                rf"\g<1>{param_value}", 
                content
            )

            if count > 0:
                content = new_content
                changes_made.append(f"{param_name}: {current_value} → {param_value}")
            else:
                if ctx:
                    await ctx.warning(f"Parameter {param_name} not found in config file")

        if not changes_made:
            return "No MCS parameters were updated. Configuration file may not contain expected MCS parameters."

        # Write updated content back to file
        target_file.write_text(content)

        changes_summary = "; ".join(changes_made)
        if ctx:
            await ctx.info(f"Updated {target_file.name} MCS parameters: {changes_summary}")

        return f"Successfully updated MCS parameters in {target_file.name}:\n{chr(10).join(changes_made)}\n\nRestart the gNB using restart_gnb tool to apply changes."

    except Exception as e:
        error_msg = f"Error updating MCS parameters: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return f"Error: {error_msg}"

@mcp.tool()
async def stop_gnb(ctx: Context = None) -> str:
    """
    Stops the currently running gNB server process.
    
    This tool executes a script that finds and stops any running gNB processes
    using graceful termination (SIGTERM) first, then force kill (SIGKILL) if needed.

    Returns:
        Status message indicating whether the stop was successful
    """
    script_path = Path(__file__).parent / "scripts" / "stop_gnb_simple.sh"
    
    if not script_path.exists():
        raise FileNotFoundError(f"Stop script not found: {script_path}")
    
    # Make sure the script is executable
    script_path.chmod(0o755)
    
    try:
        # Execute the stop script
        process = await asyncio.create_subprocess_exec(
            str(script_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            output = stdout.decode().strip()
            await ctx.info(f"gNB stop successful: {output}")
            return f"gNB process stopped successfully."
        else:
            error = stderr.decode().strip() if stderr else stdout.decode().strip()
            await ctx.warning(f"gNB stop issue: {error}")
            if process.returncode == 2:
                return "gNB process could not be force killed."
            else:
                return f"Failed to stop gNB process: {error}"
    except Exception as e:
        await ctx.error(f"Error executing stop script: {str(e)}")
        return f"Error stopping gNB process: {str(e)}"

@mcp.tool()
async def start_gnb(ctx: Context = None) -> str:
    """
    Starts the gNB server process.
    
    This tool executes a script that starts the gNB process with the current configuration.
    The gNB will be started in the background with logging to a timestamped log file.

    Returns:
        Status message indicating whether the start was successful
    """
    script_path = Path(__file__).parent / "scripts" / "start_gnb_simple.sh"
    
    if not script_path.exists():
        raise FileNotFoundError(f"Start script not found: {script_path}")
    
    # Make sure the script is executable
    script_path.chmod(0o755)
    
    try:
        # Execute the start script
        process = await asyncio.create_subprocess_exec(
            str(script_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            output = stdout.decode().strip()
            await ctx.info(f"gNB start successful: {output}")
            return f"gNB process started successfully."
        else:
            error = stderr.decode().strip() if stderr else stdout.decode().strip()
            await ctx.warning(f"gNB start issue: {error}")
            if process.returncode == 1:
                return f"Failed to start gNB process: {error}"
            else:
                return f"gNB start error: {error}"
    except Exception as e:
        await ctx.error(f"Error executing start script: {str(e)}")
        return f"Error starting gNB process: {str(e)}"

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000,
        path="/mcp",
    )