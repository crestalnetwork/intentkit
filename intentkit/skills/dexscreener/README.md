# DexScreener Skill

The DexScreener skill provides integration with the DexScreener API to search for cryptocurrency token pairs and retrieve market data including prices, volume, liquidity, and other trading metrics.

## Overview

DexScreener is a popular platform for tracking decentralized exchange (DEX) trading pairs across multiple blockchain networks. This skill enables your agent to search for token information and provide users with real-time market data.

## Skills Available

### `search_token`

Searches DexScreener for token pairs matching a query string. Supports searching by:

- Token symbol (e.g., "WIF", "DOGE")
- Token name (e.g., "Dogwifhat")
- Token address (e.g., "0x...")
- Exact ticker matching with "$" prefix (e.g., "$WIF")
- Pair address

**Parameters:**

- `query` (required): The search query string
- `sort_by` (optional): Sort results by "liquidity" (default) or "volume"
- `volume_timeframe` (optional): When sorting by volume, use "24_hour" (default), "6_hour", "1_hour", or "5_minutes"

### `get_pair_info`

Retrieves detailed information about a specific trading pair using chain ID and pair address.

**Parameters:**

- `chain_id` (required): The blockchain chain ID (e.g., "ethereum", "solana", "bsc", "polygon", "arbitrum", "base", "avalanche")
- `pair_address` (required): The trading pair contract address

### `get_token_pairs`

Finds all trading pairs for a specific token using chain ID and token address.

**Parameters:**

- `chain_id` (required): The blockchain chain ID
- `token_address` (required): The token contract address

### `get_tokens_info`

Retrieves detailed trading pair information for multiple tokens at once (up to 30 tokens).

**Parameters:**

- `chain_id` (required): The blockchain chain ID
- `token_addresses` (required): List of token contract addresses (maximum 30)

## Configuration

Add to your agent configuration:

```yaml
skills:
  dexscreener:
    enabled: true
    states:
      search_token: public # or "private" or "disabled"
      get_pair_info: public # or "private" or "disabled"
      get_token_pairs: public # or "private" or "disabled"
      get_tokens_info: public # or "private" or "disabled"
```

## Example Prompts

Here are some example prompts that will trigger the DexScreener skill:

### Basic Token Search

- "What's the current price of WIF?"
- "Show me information about Dogwifhat token"
- "Find trading pairs for PEPE"
- "Search for Solana tokens with high volume"

### Address-Based Search

- "Get token info for address 0x1234567890abcdef1234567890abcdef12345678"
- "Look up this token contract: 0xabc123..."
- "Find pairs for token address 0x..."

### Exact Ticker Matching

- "Show me all $WIF pairs" (matches only tokens with symbol "WIF")
- "Find $DOGE trading data"
- "$SOL price and volume information"

### Sorting and Filtering

- "Find highest volume tokens in the last hour"
- "Show me tokens sorted by liquidity"
- "Get 6-hour volume data for trending tokens"

### Market Analysis

- "What are the most liquid trading pairs right now?"
- "Find new token launches with high volume"
- "Show me tokens with significant price changes in the last 24 hours"
- "Compare liquidity across different DEXes for a token"

### Specific Pair Analysis

- "Get detailed info for pair address 0x1234... on Ethereum"
- "Show me the liquidity and volume for this Uniswap pair"
- "Analyze this specific trading pair on Solana"
- "What's the current price and 24h change for pair 0xabc..."

### Token Pair Discovery

- "Find all trading pairs for token 0x1234... on Ethereum"
- "Where can I trade this token? Show me all available pairs"
- "List all DEXes that have liquidity for this token address"
- "Find the best liquidity pools for token 0xabc..."

### Multi-Token Analysis

- "Compare these 5 token addresses: [list of addresses]"
- "Get trading data for my entire portfolio: [token addresses]"
- "Analyze liquidity across these tokens on Ethereum"
- "Show me pair information for these 10 tokens at once"

### Portfolio Research

- "Research this token before I invest: [token name/symbol]"
- "Is this token legitimate? Check its social links"
- "What DEXes is this token trading on?"
- "Show me the trading activity for this pair"

## Response Format

The skill returns structured JSON data containing:

- Token pair information (base/quote tokens)
- Current prices in USD and native currency
- Volume data across different timeframes
- Liquidity information
- Price change percentages
- Market cap and fully diluted valuation
- Social links and website information
- Trading transaction counts

## Rate Limits

- 300 requests per minute across all users
- Built-in rate limiting prevents exceeding API limits
- Requests are queued and processed efficiently

## Data Sources

All data is sourced from the official DexScreener API, which aggregates information from major decentralized exchanges across multiple blockchain networks including Ethereum, Solana, Binance Smart Chain, and others.
