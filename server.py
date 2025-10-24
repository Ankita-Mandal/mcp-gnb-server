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
import glob
from datetime import datetime
from action_logger import ActionLogger, make_tool_logger
from helper import extract_pdf_text, find_3gpp_document, extract_document_overview, extract_section_content, list_available_3gpp_documents, extract_pdf_toc

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
        str(PROJECT_ROOT / "oai-files")
    )
)
logger.info(f"Using configuration directory: {CONF_DIR}")
DOCUMENTATION_DIR = Path(
    os.environ.get(
        'OAI_DOCUMENTATION_DIR',
        str(PROJECT_ROOT / "oai-docs")
    )
)
logger.info(f"Using documentation directory: {DOCUMENTATION_DIR}")

KNOWLEDGE_BASE_DIR = Path(
    os.environ.get(
        'KNOWLEDGE_BASE_DIR',
        str(PROJECT_ROOT / "knowledge_base")
    )
)
logger.info(f"Using knowledge base directory: {KNOWLEDGE_BASE_DIR}")

# --- Action Log Setup (minimal wiring) ---
LOG_DIR = Path(os.environ.get("ACTION_LOG_DIR", str(PROJECT_ROOT / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)
SERVER_TYPE = os.environ.get("SERVER_TYPE", "gnb")
DEFAULT_LOG_PATH = LOG_DIR / f"{SERVER_TYPE}_action_log.jsonl"
ACTION_LOG_PATH = Path(os.environ.get("ACTION_LOG_PATH", str(DEFAULT_LOG_PATH)))
action_logger = ActionLogger(ACTION_LOG_PATH)
log_tool_calls = make_tool_logger(action_logger, SERVER_TYPE)

#-----Prompts-----
@mcp.prompt()
def improve_network_quality() -> list:
    """
    Prompt to give workflow for improving network quality of the NR5G network for higher signal strength and better performance.
    LLM should refer to OAI or 3GPP documentation for more details if required.

    Returns:
        A list containing messages to guide the LLM through the process.
    """

    prompt_text = (
        f"To improve the network quality consider the following:\n\n"
        f"1. Check current network status using get_ue_logs and get_gnb_logs to get a comprehensive overview of the network\n"
        f"2. Adjust DL and UL MCS to higher values for high throughput\n"
        f"3. Adjust transmission and reception power attenuation to lower values for high signal strength\n"
        f"4. Ask for permission before calling restart_gnb to implement the updates\n"
        f"5. Ask for permission before calling restarting the UE to reconnect it to the gnb\n"
        f"6. Verify network improvement by checking logs using get_ue_logs and get_gnb_logs\n"
    )
    
    return [{"role": "user", "content": {"type": "text", "text": prompt_text}}]

@mcp.prompt()
def save_energy_resources() -> list:
    """
    Prompt to give workflow for saving energy and resources in the NR5G network.
    LLM should refer to OAI or 3GPP documentation for more details if required.

    Returns:
        A list containing messages to guide the LLM through the process.
    """
    
    prompt_text = (
        f"To save energy and resources of the network consider the following:\n\n"
        f"1. Check current network status using get_ue_logs and get_gnb_logs to get a comprehensive overview of the network\n"
        f"2. Adjust DL and UL MCS to lower values for low throughput\n"
        f"3. Adjust transmission and reception power attenuation to higher values for low signal strength\n"
        f"4. Ask for permission before calling restart_gnb to implement the updates\n"
        f"5. Ask for permission before calling restarting the UE to reconnect it to the gnb\n"
        f"6. Verify network improvement by checking logs using get_ue_logs and get_gnb_logs\n"
    )
    
    return [{"role": "user", "content": {"type": "text", "text": prompt_text}}]

#-----Tools-----
@mcp.tool()
@log_tool_calls
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
@log_tool_calls
async def get_gnb_config(ctx: Context = None) -> str:
    """
    Retrieves the current gNB configuration in the 5G SA network.
    
    The purpose of this tool is to check if configuration modification in gnb is implemented in the .conf file.
    This cannot be used to confirm if the modification is implemented in the 5G network. Use the UE logging and gnb logging tool to get the performance metrics of the network to check if the modification is implemented. 

    This tool executes the shell script that parses the local gNB configuration file
    and returns detailed configuration information in JSON format including:
    - gNB identity (ID, name, tracking area)
    - PLMN configuration (MCC, MNC)
    - RF configuration (band, frequencies, bandwidth)
    - Power settings (SSB, PDSCH, max UE power)
    - SSB and PRACH configuration
    - Antenna configuration
    
    Validation:
    Double-check calculations against known 5G standards
    Cross-reference with 3GPP specifications or OAI documentation when interpreting parameters
    Ask for clarification when uncertain rather than making assumption
    
    Returns:
        JSON string containing the complete gNB configuration
    """
    
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
@log_tool_calls
async def get_gnb_logs(
    lines: int = 100,
    ctx: Context = None
) -> str:
    """
    Retrieves the latest gNB log file content. Log messages include information about the gNB's operation, including configuration, performance, and error messages.
    
    Log files follow the pattern: gnb_YYYY-MM-DD_HHMMSS.log
    
    - Radio measurements:
      * RSRP (Reference Signal Received Power): Signal strength in dBm, typically -44 to -140
      * RSRQ (Reference Signal Received Quality): Signal quality in dB, typically -3 to -20
      * SINR (Signal to Interference plus Noise Ratio): In dB, higher is better
      * RSSI (Received Signal Strength Indicator): Total received power in dBm
      * CQI (Channel Quality Indicator): Integer from 1-15, higher is better
      * SNR (Signal to Noise Ratio): For uplink reception quality in dB
    
    - Performance metrics:
      * DL/UL BLER (Block Error Rate): Percentage of errored blocks, lower is better
      * DL/UL Throughput: Calculated throughput in Mbps based on MCS and PRB allocation
      * DL/UL MCS (Modulation and Coding Scheme): Integer value determining modulation order
      * PRB allocation: Number of Physical Resource Blocks assigned
      * Tx/Rx bytes: Actual transmitted/received bytes at MAC layer
    
    - Power metrics:
      * Power Headroom: Available UE transmission power in dB
      * Transmission power: Current UE transmission power in dBm
    
    Args:
        lines: Number of lines to read from the end of the log file (default: 100, max: 1000)
        
    Returns:
        Content from the latest gNB log file
    """   

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

@mcp.tool()
@log_tool_calls
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
@log_tool_calls
async def update_gnb_power(
    att_tx: int = None,
    att_rx: int = None,
    ctx: Context = None
) -> str:
    """
    Updates RF attenuation parameters in the gNB .conf configuration file.
    
    This tool configures the RF attenuation parameters that control the gNB's 
    transmit and receive power levels in the RF chain. You should restart the gNB 
    to apply changes.
    
    RF Attenuation Parameters:
    - att_tx: Transmit attenuation in dB (typically 0-30 dB) - Higher values reduce transmitted RF power
    - att_rx: Receive attenuation in dB (typically 0-30 dB) - Higher values reduce receive sensitivity
    
    Args:
        att_tx: Transmit attenuation value in dB (optional, range: 0-30)
        att_rx: Receive attenuation value in dB (optional, range: 0-30)
        
    Returns:
        Confirmation message with updated parameters
    """
    # Validate parameters
    if att_tx is not None and not (0 <= att_tx <= 30):
        error_msg = f"Invalid att_tx value '{att_tx}'. Must be between 0 and 30 dB"
        if ctx:
            await ctx.error(error_msg)
        return f"Error: {error_msg}"
    
    if att_rx is not None and not (0 <= att_rx <= 30):
        error_msg = f"Invalid att_rx value '{att_rx}'. Must be between 0 and 30 dB"
        if ctx:
            await ctx.error(error_msg)
        return f"Error: {error_msg}"
    
    if att_tx is None and att_rx is None:
        error_msg = "At least one attenuation parameter (att_tx or att_rx) must be specified"
        if ctx:
            await ctx.error(error_msg)
        return f"Error: {error_msg}"
    
    # Use environment variable for config file path, with fallback
    config_file_name = os.environ.get('GNB_CONFIG_FILE', 'gnb.sa.band78.51prb.usrpb200.conf')
    
    # If it's just a filename, combine with CONF_DIR
    if '/' not in config_file_name:
        config_file_path = CONF_DIR / config_file_name
    else:
        config_file_path = Path(config_file_name)
    
    # Check if config file exists
    if not config_file_path.exists():
        error_msg = f"Configuration file not found: {config_file_path}"
        if ctx:
            await ctx.error(error_msg)
        return f"Error: {error_msg}"
    
    try:
        # Read the current configuration
        content = config_file_path.read_text()
        
        if ctx:
            await ctx.info(f"Updating RF attenuation parameters in {config_file_path.name}")
        
        # Track changes made
        changes_made = []
        
        # Update att_tx if specified
        if att_tx is not None:
            # Capture current value for logging
            current_match = re.search(r"att_tx\s*=\s*(\d+)", content)
            current_value = current_match.group(1) if current_match else "not found"
            
            # Pattern to match att_tx parameter with flexible whitespace
            pattern = r"(att_tx\s*=\s*)\d+"
            replacement = fr"\g<1>{att_tx}"
            
            new_content, count = re.subn(pattern, replacement, content)
            
            if count > 0:
                content = new_content
                changes_made.append(f"att_tx: {current_value} → {att_tx}")
                if ctx:
                    await ctx.info(f"Updated att_tx from {current_value} to {att_tx} dB")
            else:
                if ctx:
                    await ctx.warning("Parameter att_tx not found in config file")
        
        # Update att_rx if specified
        if att_rx is not None:
            # Capture current value for logging
            current_match = re.search(r"att_rx\s*=\s*(\d+)", content)
            current_value = current_match.group(1) if current_match else "not found"
            
            # Pattern to match att_rx parameter with flexible whitespace
            pattern = r"(att_rx\s*=\s*)\d+"
            replacement = fr"\g<1>{att_rx}"
            
            new_content, count = re.subn(pattern, replacement, content)
            
            if count > 0:
                content = new_content
                changes_made.append(f"att_rx: {current_value} → {att_rx}")
                if ctx:
                    await ctx.info(f"Updated att_rx from {current_value} to {att_rx} dB")
            else:
                if ctx:
                    await ctx.warning("Parameter att_rx not found in config file")
        
        if not changes_made:
            return "No RF attenuation parameters were updated. Configuration file may not contain expected attenuation parameters."
        
        # Write updated content back to file
        config_file_path.write_text(content)
        
        changes_summary = "; ".join(changes_made)
        if ctx:
            await ctx.info(f"Updated {config_file_path.name} RF attenuation parameters: {changes_summary}")
        
        return f"Successfully updated RF attenuation parameters in {config_file_path.name}:\n{chr(10).join(changes_made)}\n\nRestart the gNB using start_gnb tool to apply changes."
    
    except Exception as e:
        error_msg = f"Error updating RF attenuation parameters: {str(e)}"
        if ctx:
            await ctx.error(error_msg)
        return f"Error: {error_msg}"

@mcp.tool()
@log_tool_calls
async def stop_gnb(ctx: Context = None) -> str:
    """
    Stops the currently running gNB server process.
    
    This tool executes a script that finds and stops any running gNB processes
    using graceful termination (SIGTERM) first, then force kill (SIGKILL) if needed.
    gNB must be restarted if any configuration changes have been made.

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
@log_tool_calls
async def start_gnb(ctx: Context = None) -> str:
    """
    Starts the gNB server process.
    
    This tool executes a script that starts the gNB process with the current configuration.
    The gNB will be started in the background with logging to a timestamped log file.
    Check gnb logs after starting it to ensure it was successful.

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

@mcp.tool()
@log_tool_calls
async def get_action_log(tail: int = 200, as_json_array: bool = False) -> str:
    """Retrieve recent action log entries.
    
    This tool returns all mcp tool calls and their results for the gnb server
    
    Args:
        tail: Number of most recent lines to return (default 200). Set to 0 for full log.
        as_json_array: If True, return a JSON array string; else return JSONL text.
    
    Returns:
        The requested portion of the action log as a string.
    """
    try:
        if not ACTION_LOG_PATH.exists():
            return f"Action log not found at {ACTION_LOG_PATH}"
        lines: list[str]
        with ACTION_LOG_PATH.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        if tail and tail > 0:
            lines = lines[-tail:]
        data = [json.loads(l) for l in lines if l.strip()]
        if as_json_array:
            return json.dumps(data, ensure_ascii=False, indent=2)
        # Return as JSONL
        return "\n".join(json.dumps(x, ensure_ascii=False) for x in data)
    except Exception as e:
        logger.error("Failed to read action log: %s", e)
        return f"Error reading action log: {e}"


@mcp.tool()
@log_tool_calls
async def extract_oai_documentation(path: str) -> str:
    """Extract content from a specific OpenAirInterface documentation file.
    
    This tool allows extracting the content of a specific documentation file
    when more detailed information about OAI is needed.
    
    Args:
        path: Path to the documentation file within the repository.
              Examples: "README.md", "FEATURE_SET.md", "doc/MAC/mac-usage.md"
    
    Returns:
        Content of the requested documentation file, or an error message if the file
        cannot be found or read
    """
    if not DOCUMENTATION_DIR.exists():
        logger.error("Documentation directory not found: %s", DOCUMENTATION_DIR)
        return f"Error: Documentation directory not found: {DOCUMENTATION_DIR}"
    
    # Handle path with or without file extension
    target_path = DOCUMENTATION_DIR / path
    
    # If the path points to an existing file, return its contents
    if target_path.is_file():
        try:
            logger.info("Extracting documentation from: %s", target_path)
            return target_path.read_text()
        except Exception as e:
            logger.error("Error reading file %s: %s", target_path, e)
            return f"Error reading file: {e}"
    
    # If the path doesn't exist, try to find files matching keywords
    keywords = path.lower().split('/')[-1]  # Use the last part of the path as keywords
    matching_files = []
    
    for ext in ["*.md", "*.txt", "*.html", "*.pdf"]:
        for file in DOCUMENTATION_DIR.glob(f"**/{ext}"):
            if keywords in file.name.lower():
                matching_files.append(file)
    
    if matching_files:
        rel_paths = [str(f.relative_to(DOCUMENTATION_DIR)) for f in matching_files]
        rel_paths.sort()
        return f"File not found. Did you mean one of these?\n" + "\n".join([f"- {p}" for p in rel_paths])
    
    return f"No documentation found for '{path}'"

@mcp.tool()
@log_tool_calls
async def search_oai_documentation(keywords: str) -> str:
    """Search OpenAirInterface documentation files for specific keywords.
    
    This tool searches through all documentation files for the given keywords
    and returns a list of files containing those keywords along with matching excerpts.
    
    Args:
        keywords: Space-separated keywords to search for in documentation files
    
    Returns:
        A list of matching files and relevant excerpts, or an error message if no matches found
    """
    if not DOCUMENTATION_DIR.exists():
        logger.error("Documentation directory not found: %s", DOCUMENTATION_DIR)
        return f"Error: Documentation directory not found: {DOCUMENTATION_DIR}"
    
    if not keywords:
        return "Please provide keywords to search for."
    
    search_terms = keywords.lower().split()
    matching_files = []
    
    for ext in ["*.md", "*.txt", "*.html"]:  # Skip PDFs as they require special handling
        for file in DOCUMENTATION_DIR.glob(f"**/{ext}"):
            try:
                content = file.read_text()
                content_lower = content.lower()
                
                # Check if all search terms appear in the content
                if all(term in content_lower for term in search_terms):
                    rel_path = str(file.relative_to(DOCUMENTATION_DIR))
                    
                    # Find a relevant excerpt containing the first search term
                    term = search_terms[0]
                    pos = content_lower.find(term)
                    if pos >= 0:
                        # Extract a snippet around the match
                        start = max(0, pos - 100)
                        end = min(len(content), pos + 100)
                        
                        # Adjust to avoid cutting words
                        while start > 0 and content[start] != ' ' and content[start] != '\n':
                            start -= 1
                        while end < len(content) and content[end] != ' ' and content[end] != '\n':
                            end += 1
                        
                        excerpt = content[start:end].strip()
                        if start > 0:
                            excerpt = "..." + excerpt
                        if end < len(content):
                            excerpt = excerpt + "..."
                        
                        matching_files.append((rel_path, excerpt))
            except Exception as e:
                logger.warning("Error reading %s: %s", file, e)
    
    if matching_files:
        result = f"Found {len(matching_files)} files matching '{keywords}':\n\n"
        for path, excerpt in matching_files:
            result += f"## {path}\n{excerpt}\n\n"
        return result
    
    return f"No documentation files found containing '{keywords}'"

@mcp.tool()
@log_tool_calls
async def get_3gpp_toc(document: str, keyword: str = "") -> str:
    """
    Extract the table of contents from a 3GPP document, optionally filtered by keyword.
    Use this tool to find the page number or section number of a specific section in the document. Use the section tool to get more information about the specific section.
      The available documents are:
     - 38.101
     - 38.104
     - 38.201
     - 38.211
     - 38.214
     - 38.300
     - 38.331
    Args:
        document: 3GPP document number (e.g., "38.104", "38.211")
        keyword: Optional keyword to filter TOC entries (e.g., "bandwidth", "MIMO")
    
    Returns:
        Table of contents from the document, filtered by keyword if provided
    """
    if not KNOWLEDGE_BASE_DIR.exists():
        return f"Knowledge base directory not found: {KNOWLEDGE_BASE_DIR}"
    
    # Find matching PDF file
    doc_num = document.replace("TS ", "").replace(".", "")
    pdf_files = list(KNOWLEDGE_BASE_DIR.glob(f"*{doc_num}*.pdf"))
    
    if not pdf_files:
        available = [f.name for f in KNOWLEDGE_BASE_DIR.glob("*.pdf")]
        return f"Document TS {document} not found. Available: {available}"
    
    pdf_file = pdf_files[0]
    
    # Extract TOC from the PDF
    toc_text = extract_pdf_toc(pdf_file, keyword)
    
    if "Error reading PDF" in toc_text:
        return toc_text
    
    # Format the response
    keyword_info = f" filtered by '{keyword}'" if keyword else ""
    return f"# Table of Contents for TS {document}{keyword_info}\n**File:** {pdf_file.name}\n\n{toc_text}\n\n*Use get_3gpp_section with a section number to view specific content*"

# @mcp.tool()
# @log_tool_calls
# async def get_3gpp_section(document: str, section: str = "") -> str:
#     """Extract content from a 3GPP document, optionally by section number."""
#     if not KNOWLEDGE_BASE_DIR.exists():
#         return f"Knowledge base directory not found: {KNOWLEDGE_BASE_DIR}"
    
#     # Find matching PDF file
#     doc_num = document.replace("TS ", "").replace(".", "")
#     pdf_files = list(KNOWLEDGE_BASE_DIR.glob(f"*{doc_num}*.pdf"))
    
#     if not pdf_files:
#         available = [f.name for f in KNOWLEDGE_BASE_DIR.glob("*.pdf")]
#         return f"Document TS {document} not found. Available: {available}"
    
#     pdf_file = pdf_files[0]
    
#     # Extract text from the PDF
#     full_text = extract_pdf_text(pdf_file)
    
#     if "Error reading PDF" in full_text:
#         return full_text
    
#     # If no section specified, return a preview of the document content
#     if not section.strip():
#         preview = full_text[:4000]  # First 4000 characters
#         return f"# TS {document}\n**File:** {pdf_file.name}\n\n{preview}\n\n*Specify section parameter for specific content*"
    
#     # Look for the section in the extracted text
#     # This pattern looks for section numbers at the start of a line or after a page marker
#     section_pattern = re.compile(f"(^|---\\s+PAGE\\s+\\d+\\s+---\\s*\\n)\\s*{re.escape(section)}\\s+[A-Z]", re.MULTILINE)
#     match = section_pattern.search(full_text)
    
#     if match:
#         # Get the position where the section starts
#         start_pos = match.start()
        
#         # Extract a reasonable amount of text after the section start
#         section_text = full_text[start_pos:start_pos + 4000]
        
#         return f"# TS {document} - Section {section}\n**File:** {pdf_file.name}\n\n{section_text}"
    
#     return f"Section {section} not found in TS {document}. Try a different section number."

@mcp.tool()
@log_tool_calls
async def get_3gpp_section(document: str, section: str = "", ctx: Context = None) -> str:
    """
    Extract content from a specific 3GPP document and optionally a specific section.
    
    Args:
        document: 3GPP document number (e.g., "38.104", "38.211", "23.501")
        section: Optional section number (e.g., "5", "5.4", "5.4.3")
    
    Returns:
        Text content from the document or specific section
    """
    # Find the document using helper function
    pdf_file, error_msg = find_3gpp_document(KNOWLEDGE_BASE_DIR, document)
    if error_msg:
        if ctx:
            await ctx.error(error_msg)
        return f"Error: {error_msg}"
    
    if ctx:
        await ctx.info(f"Extracting content from {pdf_file.name}")
    
    # Extract text from PDF using helper function
    full_text = extract_pdf_text(pdf_file)
    
    if "Error reading PDF" in full_text:
        if ctx:
            await ctx.error(f"Failed to read PDF: {pdf_file.name}")
        return full_text
    
    # Extract content based on whether section is specified
    if not section.strip():
        # Return document overview
        if ctx:
            await ctx.info(f"Returning document overview for TS {document}")
        return extract_document_overview(full_text, document, pdf_file)
    else:
        # Extract specific section
        if ctx:
            await ctx.info(f"Searching for section {section} in TS {document}")
        result = extract_section_content(full_text, section, document, pdf_file)
        
        if result.startswith("Error:"):
            if ctx:
                await ctx.warning(result)
        else:
            if ctx:
                await ctx.info(f"Successfully extracted section {section} from TS {document}")
        
        return result

# --- Resources ---
@mcp.resource("oai://action-log")
def action_log_resource() -> str:
    """Expose recent action log entries as a resource (JSONL tail).
    
    Returns the last 200 lines of the action log as JSONL for quick inspection.
    Use the `get_action_log` tool for custom tail sizes or JSON array format.
    """
    try:
        if not ACTION_LOG_PATH.exists():
            return f"Action log not found at {ACTION_LOG_PATH}"
        with ACTION_LOG_PATH.open("r", encoding="utf-8") as f:
            lines = f.readlines()[-200:]
        return "\n".join(line.rstrip("\n") for line in lines)
    except Exception as e:
        logger.error("Failed to read action log: %s", e)
        return f"Error reading action log: {e}"

@mcp.resource("oai://docs")
def list_oai_documentation() -> str:
    """List all available OpenAirInterface documentation files.
    
    This resource provides a list of all documentation files available in the OAI
    repository to give context about what documentation is available.
    
    Returns:
        A formatted string listing all available documentation files with their paths
    """
    if not DOCUMENTATION_DIR.exists():
        logger.error("Documentation directory not found: %s", DOCUMENTATION_DIR)
        return f"Error: Documentation directory not found: {DOCUMENTATION_DIR}"
    
    files = []
    for ext in ["*.md", "*.txt", "*.html", "*.pdf"]:
        files.extend(list(DOCUMENTATION_DIR.glob(f"**/{ext}")))
    
    if not files:
        return f"No documentation files found in {DOCUMENTATION_DIR}"
    
    # Create a formatted list of relative paths
    rel_paths = [str(f.relative_to(DOCUMENTATION_DIR)) for f in files]
    rel_paths.sort()
    logger.info("Listed %d documentation files", len(files))
    return "Available documentation files:\n" + "\n".join([f"- {p}" for p in rel_paths])



if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000,
        path="/mcp",
    )