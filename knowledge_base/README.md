# 3GPP Knowledge Base

## Naming Convention

Use this naming format for 3GPP documents:

**Format:** `ts_<series><document>v<version>p.pdf`

**Examples:**
- `ts_138104v180900p.pdf` → TS 38.104 v18.09.00
- `ts_138211v170200p.pdf` → TS 38.211 v17.02.00  
- `ts_235010v180300p.pdf` → TS 23.501 v18.03.00

## Usage

Use the `get_3gpp_section` tool:

```
get_3gpp_section("38.104", "5.4.3.1")
```

This will:
1. Find the TS 38.104 document
2. Extract section 5.4.3.1 
3. Return the content to the LLM client
