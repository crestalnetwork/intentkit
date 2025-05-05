# Enso Finance Skills

Integration with Enso Finance API for DeFi protocols, portfolio management, and yield optimization.

## Skills

| Skill | Description |
|-------|-------------|
| `enso_get_networks` | List supported networks |
| `enso_get_tokens` | Get token info (APY, symbol, address) |
| `enso_get_prices` | Get token prices |
| `enso_get_wallet_balances` | Get wallet token balances |
| `enso_get_wallet_approvals` | Get token spend approvals |
| `enso_wallet_approve` | Broadcast approval transactions |
| `enso_route_shortcut` | Broadcast route transactions |
| `enso_get_best_yield` | Find best yield options across protocols |

## Configuration

```yaml
# Agent configuration example
skills:
  enso:
    enabled: true
    api_token: "${ENSO_API_TOKEN}"  # Optional if set at system level
    main_tokens: ["USDC", "ETH", "USDT"]
    states:
      get_networks: public
      get_tokens: public
      get_prices: public
      get_best_yield: public
      # Sensitive operations should be private or disabled
      get_wallet_approvals: private
      get_wallet_balances: private
      wallet_approve: private
      route_shortcut: disabled
```

## Get Best Yield Skill

Finds highest yield options for a token across protocols. Default: USDC on Base network.

### Parameters

- `token_symbol`: Token symbol (default: "USDC")
- `chain_id`: Blockchain network ID (default: 8453 for Base)
- `top_n`: Number of options to return (default: 5)

### Example

```
# Query: What are the best USDC yield options on Base?

# Response format:
{
  "best_options": [
    {
      "protocol_name": "Protocol Name",
      "token_name": "Token Name",
      "apy": 12.5,
      "tvl": 5000000,
      "underlying_tokens": ["USDC"]
    },
    // Additional results...
  ],
  "token_symbol": "USDC",
  "chain_name": "Base"
}
```

The skill fetches protocols, retrieves token data, filters for the target token, and sorts by APY.

## Authentication

Requires an Enso API token in agent config or system config.