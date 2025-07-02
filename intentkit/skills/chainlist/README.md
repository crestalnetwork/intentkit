# Chainlist Skill

This skill provides access to the Chainlist API, allowing agents to lookup blockchain RPC endpoints and network information.

## Features

- Look up blockchain networks by name, symbol, or chain ID
- Find RPC endpoints for any EVM-compatible blockchain
- Filter for no-tracking RPC endpoints
- Get network details including native currency, explorers, and more

## Usage

Enable this skill in your agent configuration:

```json
{
  "skills": {
    "chainlist": {
      "states": {
        "chain_lookup": "public"
      }
    }
  }
}
```

## Example Prompts

- "Find RPC endpoints for Ethereum"
- "What are the RPC endpoints for chain ID 137?"
- "Show me privacy-focused RPC endpoints for Arbitrum"
- "Get details for the Polygon network"
- "Look up information about BSC chain"

## Data Source

This skill uses data from [chainlist.org](https://chainlist.org), which provides a comprehensive list of EVM networks and their RPC endpoints. 