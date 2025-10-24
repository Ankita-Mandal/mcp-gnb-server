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
- **OAI Documentation Search**: Search and extract OpenAirInterface documentation with keyword matching

### Network Optimization Workflows
- **Performance Enhancement**: Guided workflows for improving network quality and signal strength
- **Energy Conservation**: Automated procedures for reducing power consumption and resource usage
- **Intelligent Recommendations**: Context-aware suggestions based on current network status

### Comprehensive Logging & Monitoring
- **Action Logger**: Thread-safe JSONL logging of all MCP tool calls with performance metrics
- **Automatic Log Rotation**: 5MB file size limits with automatic rotation
- **Performance Tracking**: Execution duration, success/failure rates, and error details
- **Audit Trail**: Complete history of all configuration changes and operations

## Architecture

### Modular Design
```
gnb_mcpserver/
├── server.py              # Main MCP server with 12 tools + 2 prompts + 2 resources
├── helper.py              # PDF processing and document extraction utilities
├── action_logger.py       # Thread-safe logging with rotation and decorators
├── requirements.txt       # Python dependencies
├── docker-compose.yml     # Docker deployment configuration
├── logs/                  # Action logs directory
└── knowledge_base/        # 3GPP PDF documents storage
```

### Clean Separation of Concerns
- **server.py**: MCP tool definitions, prompts, FastMCP integration, environment configuration
- **helper.py**: PDF processing, document extraction, content parsing logic
- **action_logger.py**: Logging infrastructure, decorators, thread-safe operations

## MCP Capabilities

### Tools (12 Total)

#### Configuration Management
1. **`update_gnb_bandwidth`** - Configure bandwidth (10MHz/20MHz) with automatic BWP settings
2. **`update_gnb_mcs`** - Set downlink/uplink MCS parameters (0-28 range)
3. **`update_gnb_power`** - Adjust RF attenuation (att_tx, att_rx) parameters (0-30 dB)
4. **`get_gnb_config`** - Retrieve current gNB configuration as JSON

#### Process Management
5. **`start_gnb`** - Start gNB process with logging
6. **`stop_gnb`** - Stop gNB process with graceful termination
7. **`get_gnb_logs`** - Retrieve gNB operational logs (configurable lines: 1-1000)

#### Documentation Access
8. **`get_3gpp_toc`** - Extract table of contents from 3GPP documents with keyword filtering
9. **`get_3gpp_section`** - Extract content from 3GPP standards documents
10. **`extract_oai_documentation`** - Get specific OAI documentation files
11. **`search_oai_documentation`** - Search OAI docs with keyword matching

#### Monitoring
12. **`get_action_log`** - Retrieve MCP action logs (JSONL or JSON array format)

### Prompts (2 Total)

1. **`improve_network_quality`** - Workflow guidance for enhancing network performance and signal strength
2. **`save_energy_resources`** - Procedures for optimizing power consumption and resource utilization

### Resources (2 Total)

1. **`oai://action-log`** - Expose recent action log entries as JSONL resource
2. **`oai://docs`** - List all available OpenAirInterface documentation files

## Docker Deployment

### Prerequisites
- Docker and Docker Compose installed
- OpenAirInterface 5G repository cloned and built
- USRP hardware connected (for actual gNB operations)

### Quick Start
```bash
# Navigate to project directory
cd gnb_mcpserver

# Start the MCP server
docker-compose up -d

# Monitor server status
docker-compose logs -f gnb-mcp-server
```

### Container Configuration
The server runs with host networking and the following volume mounts:
- **Configuration files**: `./oai-files` → gNB configuration access
- **Documentation**: `./oai-docs` → OAI documentation library
- **Knowledge base**: `./knowledge_base` → 3GPP PDF documents
- **Logs**: `./logs` → Persistent action logging


### Supported 3GPP Documents
- **TS 38.101** - UE radio transmission and reception
- **TS 38.104** - Base Station radio transmission and reception
- **TS 38.201** - Physical layer general description
- **TS 38.211** - Physical channels and modulation
- **TS 38.214** - Physical layer procedures for data
- **TS 38.300** - NR overall description
- **TS 38.331** - Radio Resource Control protocol

## Action Logging

All MCP operations are automatically logged with:
- **Timestamp** (ISO format with timezone)
- **Tool/prompt name** and sanitized arguments
- **Execution duration** in milliseconds
- **Success/failure status** with error details
- **Results** (truncated for large outputs)

**Format**: JSONL (one JSON object per line)  
**Location**: `logs/gnb_action_log.jsonl`  
**Rotation**: Automatic at 5MB file size

### Performance Features
- Thread-safe logging with minimal overhead
- Efficient PDF processing with intelligent content extraction
- Optimized regex patterns for configuration updates
- Smart document discovery with pattern matching
- Host networking for optimal performance

## License

This project is part of the OpenAirInterface 5G ecosystem and follows the same licensing terms.

## Support

For technical assistance:
- **gNB Configuration**: Review OAI documentation and operational logs
- **MCP Tools**: Examine action logs for detailed execution information
- **3GPP Standards**: Verify document availability in knowledge_base directory
- **Container Issues**: Check Docker logs and volume mount configurations

