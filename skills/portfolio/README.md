# Blockchain Portfolio Analysis Skills

A set of skills for analyzing blockchain wallets and portfolios through the Moralis API, allowing agents to retrieve wallet data, token balances, and investment performance across various blockchain networks.

## Available Skills

| Skill | Description | Endpoint | Example Prompts |
|-------|-------------|----------|----------------|
| `wallet_history` | Gets transaction history including sends, receives, token transfers | `GET /wallets/{address}/history` | "Show me all transactions for wallet 0x123..." <br> "What are the recent transactions for this ETH address?" |
| `token_balances` | Gets token balances and USD value with spam filtering options | `GET /wallets/{address}/tokens` | "What tokens does wallet 0x123 hold?" <br> "Show me token balances with USD values for this address" |
| `wallet_approvals` | Lists active ERC20 token approvals to identify spend permissions | `GET /wallets/{address}/approvals` | "Check what contracts have approval to spend from wallet 0x123" <br> "Has this wallet approved any token spending?" |
| `wallet_swaps` | Lists all swap-related transactions (buy/sell) for trade analysis | `GET /wallets/{address}/swaps` | "Show me all token swaps for wallet 0x123" <br> "What trading activity has this address performed?" |
| `wallet_net_worth` | Calculates total wallet value in USD across multiple chains | `GET /wallets/{address}/net-worth` | "What's the total value of wallet 0x123?" <br> "Calculate the net worth of this address across all chains" |
| `wallet_profitability_summary` | Provides overview of wallet profitability metrics | `GET /wallets/{address}/profitability/summary` | "Is wallet 0x123 profitable overall?" <br> "Give me a summary of trading performance for this address" |
| `wallet_profitability` | Delivers detailed profitability by token with buy/sell prices | `GET /wallets/{address}/profitability` | "Show detailed profit/loss for each token in wallet 0x123" <br> "What's the cost basis of tokens in this wallet?" |
| `wallet_stats` | Provides statistics about NFTs, collections, and transactions | `GET /wallets/{address}/stats` | "How many NFTs does wallet 0x123 have?" <br> "Give me stats about this wallet's activity" |
| `wallet_defi_positions` | Get DeFi positions for a wallet | `GET /wallets/{address}/defi/positions` | "What DeFi positions does my wallet have?" <br> "Show my liquidity positions." |
| `wallet_nfts` | Get NFTs owned by a wallet address | `GET /{address}/nft` | "What NFTs does wallet 0x123 own?" <br> "Show me all the NFTs in my wallet." |

All endpoints use the base URL defined in `constants.py`: `https://deep-index.moralis.io/api/v2.2`

## Migration Note

If you're currently using the Moralis module, simply update your configuration by changing `moralis:` to `portfolio:`. All functionality remains identical.

## Authentication

All API requests include the Moralis API key in the header:
```
X-API-Key: YOUR_MORALIS_API_KEY
```

## Supported Chains

These skills support various EVM-compatible chains:
- Ethereum (eth)
- Polygon (polygon)
- Binance Smart Chain (bsc)
- Avalanche (avalanche)
- Arbitrum (arbitrum)
- Optimism (optimism)
- Base (base)

## Key Parameters

Most endpoints support these common parameters:
- `chain`: The chain to query (default: eth)
- `limit`: Number of results per page
- `cursor`: Pagination cursor for subsequent requests

## Getting a Moralis API Key

1. Create an account at [Moralis.io](https://moralis.io/)
2. Navigate to the API Keys section in your dashboard
3. Create a new key with appropriate permissions
