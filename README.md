# gNB MCP Server

A comprehensive **Model Context Protocol (MCP) server** for managing OpenAirInterface 5G gNodeB (gNB) configurations, operations, and documentation access. This server provides intelligent tools for gNB configuration management, RF parameter control, 3GPP standards reference, and comprehensive action logging.

## Features

### gNB Configuration Management
- **Bandwidth Control**: Configure 10MHz/20MHz bandwidth with automatic BWP parameter adjustment
- **MCS Configuration**: Set downlink/uplink Modulation and Coding Scheme parameters (0-28 range)
- **RF Power Control**: Adjust transmit/receive attenuation parameters (att_tx, att_rx) for RF chain optimization
- **Real-time Configuration**: Live configuration reading and validation

### Process Management
- **gNB Lifecycle**: Start/stop gNB processes with proper signal handling
- **Log Monitoring**: Real-time access to gNB operational logs with configurable tail length
- **Status Tracking**: Process status monitoring and error reporting

### Documentation & Standards Access
- **3GPP Standards Integration**: Extract content from 3GPP specification documents (TS 38.104, 38.211, 38.300, etc.)
- **Section-specific Extraction**: Retrieve specific sections or document overviews from PDF standards
- **OAI Documentation Search**: Search and extract OpenAirInterface documentation with keyword matching
- **Smart Content Discovery**: Intelligent document finding and content extraction

### Comprehensive Logging & Monitoring
- **Action Logger**: Thread-safe JSONL logging of all MCP tool calls with performance metrics
- **Automatic Log Rotation**: 5MB file size limits with automatic rotation
- **Performance Tracking**: Execution duration, success/failure rates, and error details
- **Audit Trail**: Complete history of all configuration changes and operations

## Architecture

### Modular Design
```
gnb_mcpserver/
├── server.py              # Main MCP server with 11 tools + 2 resources
├── helper.py              # PDF processing and document extraction utilities
├── action_logger.py       # Thread-safe logging with rotation and decorators
├── requirements.txt       # Python dependencies
├── docker-compose.yml     # Docker deployment configuration
├── logs/                  # Action logs directory
└── knowledge_base/        # 3GPP PDF documents storage
```

### Clean Separation of Concerns
- **server.py**: MCP tool definitions, FastMCP integration, environment configuration
- **helper.py**: PDF processing, document extraction, content parsing logic
- **action_logger.py**: Logging infrastructure, decorators, thread-safe operations

## MCP Tools (11 Total)

### Configuration Tools
1. **`update_gnb_bandwidth`** - Configure bandwidth (10MHz/20MHz) with automatic BWP settings
2. **`update_gnb_mcs`** - Set downlink/uplink MCS parameters (0-28 range)
3. **`update_gnb_power`** - Adjust RF attenuation (att_tx, att_rx) parameters (0-30 dB)
4. **`get_gnb_config`** - Retrieve current gNB configuration as JSON

### Process Management Tools
5. **`start_gnb`** - Start gNB process with logging
6. **`stop_gnb`** - Stop gNB process with graceful termination
7. **`get_gnb_logs`** - Retrieve gNB operational logs (configurable lines: 1-1000)

### Documentation Tools
8. **`get_3gpp_section`** - Extract content from 3GPP standards documents
9. **`extract_oai_documentation`** - Get specific OAI documentation files
10. **`search_oai_documentation`** - Search OAI docs with keyword matching

### Monitoring Tools
11. **`get_action_log`** - Retrieve MCP action logs (JSONL or JSON array format)

## MCP Resources (2 Total)

1. **`oai://action-log`** - Expose recent action log entries as JSONL resource
2. **`oai://docs`** - List all available OpenAirInterface documentation files

## Docker Deployment

### Prerequisites
- Docker and Docker Compose installed
- OpenAirInterface 5G repository cloned and built
- USRP hardware connected (for actual gNB operations)

### Quick Start
```bash
# Clone and navigate to the project
cd gnb_mcpserver

# Start the MCP server
docker-compose up -d

# Check server status
docker-compose logs -f gnb-mcp-server
```

### Docker Configuration
The server runs in a Docker container with the following mounts:
- **Configuration files**: `/home/.../conf_files` → `/app/oai-files`
- **Documentation**: `/home/.../doc` → `/app/oai-docs`
- **Logs**: `./logs` → `/app/logs`
- **Knowledge base**: `./knowledge_base` → `/app/knowledge_base`

## Configuration

### Environment Variables
```bash
# Configuration paths
OAI_CONF_DIR=/app/oai-files                    # gNB config files location
OAI_DOCUMENTATION_DIR=/app/oai-docs            # OAI documentation path
KNOWLEDGE_BASE_DIR=/app/knowledge_base         # 3GPP documents path

# Logging configuration
ACTION_LOG_DIR=/app/logs                       # Action logs directory
ACTION_LOG_PATH=/app/logs/gnb_action_log.jsonl # Specific log file
SERVER_TYPE=gnb                                # Server type identifier

# gNB configuration
GNB_CONFIG_FILE=gnb.sa.band78.51prb.usrpb200.conf # Default config file
```

### Supported 3GPP Documents
- **TS 38.101** - UE radio transmission and reception
- **TS 38.104** - Base Station radio transmission and reception
- **TS 38.201** - Physical layer general description
- **TS 38.211** - Physical channels and modulation
- **TS 38.300** - NR overall description
- **TS 38.331** - Radio Resource Control protocol

## Usage Examples

### Basic gNB Configuration
```python
# Update bandwidth configuration
await update_gnb_bandwidth("20MHz")

# Set MCS parameters
await update_gnb_mcs(dl_mcs=16, ul_mcs=12)

# Adjust RF power attenuation
await update_gnb_power(att_tx=15, att_rx=10)

# Restart gNB to apply changes
await stop_gnb()
await start_gnb()
```

### Documentation Access
```python
# Get 3GPP document overview
await get_3gpp_section("38.104")

# Extract specific section
await get_3gpp_section("38.104", "5.4")

# Search OAI documentation
await search_oai_documentation("MAC scheduler configuration")

# Get specific documentation file
await extract_oai_documentation("doc/MAC/mac-usage.md")
```

### Monitoring & Logging
```python
# Check gNB logs
await get_gnb_logs(lines=200)

# Review action history
await get_action_log(tail=100, as_json_array=True)

# Get current configuration
config = await get_gnb_config()
```

## Development

### Dependencies
```bash
pip install -r requirements.txt
```

**Required packages:**
- `fastmcp>=2.12.2` - MCP framework
- `httpx>=0.28.1` - HTTP client
- `mcp[cli]>=1.13.1` - MCP CLI tools
- `PyPDF2>=3.0.0` - PDF processing for 3GPP documents

### Local Development
```bash
# Run server locally
python server.py

# Server will be available at:
# http://localhost:8000/mcp
```

### Testing
```bash
# Test MCP tools
mcp list-tools http://localhost:8000/mcp

# Test specific tool
mcp call http://localhost:8000/mcp get_gnb_config
```

## Action Logging

All MCP tool calls are automatically logged with:
- **Timestamp** (ISO format with timezone)
- **Tool name** and sanitized arguments
- **Execution duration** in milliseconds
- **Success/failure status** with error details
- **Results** (truncated for large outputs)

**Log format**: JSONL (one JSON object per line)
**Location**: `logs/gnb_action_log.jsonl`
**Rotation**: Automatic at 5MB file size

## Error Handling

### Comprehensive Validation
- Parameter range validation (MCS: 0-28, Power: 0-30 dB, etc.)
- File existence checks before operations
- Safe regex-based configuration updates
- Process execution error handling

### User-Friendly Feedback
- Context logging for real-time user feedback
- Detailed error messages with suggestions
- Graceful fallback for missing files/directories

## Production Deployment

### Health Monitoring
```bash
# Monitor action logs
tail -f logs/gnb_action_log.jsonl

# Check server health
curl http://localhost:8000/mcp/health

# View recent errors
grep '"status":"error"' logs/gnb_action_log.jsonl
```

### Performance Optimization
- Thread-safe logging with minimal overhead
- Efficient PDF processing with content caching
- Optimized regex patterns for configuration updates
- Smart file discovery with pattern matching

## License

This project is part of the OpenAirInterface 5G ecosystem and follows the same licensing terms.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add comprehensive tests for new tools
4. Update documentation
5. Submit a pull request

## Support

For issues related to:
- **gNB configuration**: Check OAI documentation and logs
- **MCP tools**: Review action logs for detailed error information
- **3GPP standards**: Verify document availability in knowledge_base/
- **Docker deployment**: Check container logs and mount points

---
