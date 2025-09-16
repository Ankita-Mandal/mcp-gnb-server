#!/bin/bash

# get_gnb_config.sh
# Returns gNB configuration from local OAI 5G network configuration file in JSON format

# Use environment variables for configuration paths with fallbacks
OAI_CONF_DIR="${OAI_CONF_DIR:-/home/xmili/Documents/Abhiram/USRPworkarea/oai-setup/openairinterface5g/ci-scripts/conf_files}"
GNB_CONFIG_FILE="${GNB_CONFIG_FILE:-gnb.sa.band78.51prb.usrpb200.conf}"

# If GNB_CONFIG_FILE is just a filename, combine with OAI_CONF_DIR
if [[ "$GNB_CONFIG_FILE" != *"/"* ]]; then
    CONFIG_FILE="$OAI_CONF_DIR/$GNB_CONFIG_FILE"
else
    CONFIG_FILE="$GNB_CONFIG_FILE"
fi

# Function to extract parameter value from config file
extract_param() {
    local param_name="$1"
    local config_content="$2"
    
    # Extract parameter value, handling various formats
    local value=$(echo "$config_content" | grep -E "^\s*${param_name}\s*=" | head -1 | sed -E 's/.*=\s*([^;#]*).*/\1/' | sed 's/[[:space:]]*$//' | sed 's/^[[:space:]]*//')
    
    # Remove quotes if present
    value=$(echo "$value" | sed 's/^"//;s/"$//')
    
    if [[ -z "$value" ]]; then
        echo "null"
    else
        echo "$value"
    fi
}

# Function to extract gNB configuration
extract_gnb_config() {
    local config="$1"
    
    # Extract basic gNB identity
    local gnb_id=$(extract_param "gNB_ID" "$config")
    local gnb_name=$(extract_param "gNB_name" "$config")
    local tracking_area_code=$(extract_param "tracking_area_code" "$config")
    
    # Extract PLMN information
    local mcc=$(extract_param "mcc" "$config")
    local mnc=$(extract_param "mnc" "$config")
    local mnc_length=$(extract_param "mnc_length" "$config")
    
    # Extract RF configuration
    local band=$(extract_param "dl_frequencyBand" "$config")
    local point_a_frequency=$(extract_param "dl_absoluteFrequencyPointA" "$config")
    local ssb_frequency=$(extract_param "dl_absoluteFrequencySSB" "$config")
    local dl_bandwidth_prbs=$(extract_param "dl_carrierBandwidth" "$config")
    local ul_bandwidth_prbs=$(extract_param "ul_carrierBandwidth" "$config")
    local dl_bwp_location=$(extract_param "initialDLBWPlocationAndBandwidth" "$config")
    local ul_bwp_location=$(extract_param "initialULBWPlocationAndBandwidth" "$config")
    
    # Extract subcarrier spacing (numerology)
    local dl_scs=$(extract_param "dl_subcarrierSpacing" "$config")
    local ul_scs=$(extract_param "ul_subcarrierSpacing" "$config")
    
    # Convert SCS values to actual frequencies
    case $dl_scs in
        "0") dl_scs_khz="15" ;;
        "1") dl_scs_khz="30" ;;
        "2") dl_scs_khz="60" ;;
        "3") dl_scs_khz="120" ;;
        *) dl_scs_khz="unknown" ;;
    esac
    
    case $ul_scs in
        "0") ul_scs_khz="15" ;;
        "1") ul_scs_khz="30" ;;
        "2") ul_scs_khz="60" ;;
        "3") ul_scs_khz="120" ;;
        *) ul_scs_khz="unknown" ;;
    esac
    
    # Extract power settings
    local ssb_power=$(extract_param "ssPBCH_BlockPower" "$config")
    local pdsch_power=$(extract_param "referenceSignalPower" "$config")
    local p_max=$(extract_param "pMax" "$config")
    
    # Extract SSB configuration
    local ssb_period=$(extract_param "ssb_periodicityServingCell" "$config")
    case $ssb_period in
        "0") ssb_period_ms="5" ;;
        "1") ssb_period_ms="10" ;;
        "2") ssb_period_ms="20" ;;
        "3") ssb_period_ms="40" ;;
        "4") ssb_period_ms="80" ;;
        "5") ssb_period_ms="160" ;;
        *) ssb_period_ms="unknown" ;;
    esac
    
    # Extract PRACH configuration
    local prach_config_index=$(extract_param "prach_ConfigurationIndex" "$config")
    local prach_msg1_fdm=$(extract_param "prach_msg1_FDM" "$config")
    local prach_freq_start=$(extract_param "prach_msg1_FrequencyStart" "$config")
    local zero_correlation_zone=$(extract_param "zeroCorrelationZoneConfig" "$config")
    local preamble_received_power=$(extract_param "preambleReceivedTargetPower" "$config")
    local preamble_trans_max=$(extract_param "preambleTransMax" "$config")
    local power_ramping_step=$(extract_param "powerRampingStep" "$config")
    local ra_response_window=$(extract_param "ra_ResponseWindow" "$config")
    
    # Extract MIMO configuration (if available)
    local pdsch_ant_ports=$(extract_param "pdsch_AntennaPorts" "$config")
    local pusch_ant_ports=$(extract_param "pusch_AntennaPorts" "$config")
    
    # Calculate bandwidth in MHz from PRBs (approximate)
    local dl_bandwidth_mhz="unknown"
    local ul_bandwidth_mhz="unknown"
    
    if [[ "$dl_bandwidth_prbs" != "null" && "$dl_scs_khz" != "unknown" ]]; then
        case "$dl_scs_khz" in
            "15") dl_bandwidth_mhz=$(awk "BEGIN {printf \"%.1f\", $dl_bandwidth_prbs * 0.18}") ;;
            "30") dl_bandwidth_mhz=$(awk "BEGIN {printf \"%.1f\", $dl_bandwidth_prbs * 0.36}") ;;
            "60") dl_bandwidth_mhz=$(awk "BEGIN {printf \"%.1f\", $dl_bandwidth_prbs * 0.72}") ;;
            "120") dl_bandwidth_mhz=$(awk "BEGIN {printf \"%.1f\", $dl_bandwidth_prbs * 1.44}") ;;
        esac
    fi
    
    if [[ "$ul_bandwidth_prbs" != "null" && "$ul_scs_khz" != "unknown" ]]; then
        case "$ul_scs_khz" in
            "15") ul_bandwidth_mhz=$(awk "BEGIN {printf \"%.1f\", $ul_bandwidth_prbs * 0.18}") ;;
            "30") ul_bandwidth_mhz=$(awk "BEGIN {printf \"%.1f\", $ul_bandwidth_prbs * 0.36}") ;;
            "60") ul_bandwidth_mhz=$(awk "BEGIN {printf \"%.1f\", $ul_bandwidth_prbs * 0.72}") ;;
            "120") ul_bandwidth_mhz=$(awk "BEGIN {printf \"%.1f\", $ul_bandwidth_prbs * 1.44}") ;;
        esac
    fi
    
    # Build final JSON
    cat << EOF
{
    "timestamp": "$(date -Iseconds)",
    "gnb_identity": {
        "gnb_id": "$gnb_id",
        "gnb_name": "$gnb_name",
        "tracking_area_code": "$tracking_area_code"
    },
    "plmn_configuration": {
        "mcc": "$mcc",
        "mnc": "$mnc",
        "mnc_length": "$mnc_length"
    },
    "rf_configuration": {
        "band": "$band",
        "dl_point_a_frequency": "$point_a_frequency",
        "dl_ssb_frequency": "$ssb_frequency",
        "dl_bandwidth_prbs": "$dl_bandwidth_prbs",
        "ul_bandwidth_prbs": "$ul_bandwidth_prbs",
        "dl_bandwidth_mhz": "$dl_bandwidth_mhz",
        "ul_bandwidth_mhz": "$ul_bandwidth_mhz",
        "dl_bwp_location": "$dl_bwp_location",
        "ul_bwp_location": "$ul_bwp_location",
        "dl_subcarrier_spacing_khz": "$dl_scs_khz",
        "ul_subcarrier_spacing_khz": "$ul_scs_khz"
    },
    "power_settings": {
        "ssb_power_dbm": "$ssb_power",
        "pdsch_reference_power_dbm": "$pdsch_power",
        "max_ue_power_dbm": "$p_max",
        "description": "SSB power affects RSRP measurements, PDSCH power affects data channel performance"
    },
    "ssb_configuration": {
        "ssb_periodicity_value": "$ssb_period",
        "ssb_period_ms": "$ssb_period_ms",
        "description": "SSB broadcast periodicity affects initial access and mobility"
    },
    "prach_configuration": {
        "configuration_index": "$prach_config_index",
        "msg1_fdm": "$prach_msg1_fdm",
        "frequency_start": "$prach_freq_start",
        "zero_correlation_zone": "$zero_correlation_zone",
        "preamble_received_target_power": "$preamble_received_power",
        "preamble_trans_max": "$preamble_trans_max",
        "power_ramping_step": "$power_ramping_step",
        "ra_response_window": "$ra_response_window"
    },
    "antenna_configuration": {
        "pdsch_antenna_ports": "$pdsch_ant_ports",
        "pusch_antenna_ports": "$pusch_ant_ports",
        "description": "Antenna port configuration for MIMO support"
    }
}
EOF
}

# Main execution
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo '{"error": "Configuration file not found: '$CONFIG_FILE'", "environment": {"oai_conf_dir": "'$OAI_CONF_DIR'", "gnb_config_file": "'$GNB_CONFIG_FILE'"}}'
    exit 1
fi

config_content=$(cat "$CONFIG_FILE")
if [[ -z "$config_content" ]]; then
    echo '{"error": "Configuration file is empty or unreadable", "config_file": "'$CONFIG_FILE'"}'
    exit 1
fi

extract_gnb_config "$config_content"
