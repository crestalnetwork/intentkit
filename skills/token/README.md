# Token Skills

The Token skills provide blockchain token analytics capabilities powered by Moralis. These skills allow you to search, analyze, and track token information across multiple blockchains.

## Available Skills

| Skill | Description | Endpoint | Example Prompts |
|-------|-------------|----------|----------------|
| `token_price` | Get token price and information | `GET /erc20/:address/price` | "What's the current price of PEPE token?" "Get the price of USDT on Ethereum." |
| `token_erc20_transfers` | Get ERC20 token transfers for a wallet | `GET /:address/erc20/transfers` | "Show me all the USDT transfers for my wallet." "What are the recent token transactions for 0x123?" |
| `token_search` * | Search for tokens by name, symbol, or address | `GET /tokens/search` | "Find tokens with 'pepe' in the name." "Search for tokens with high market cap on Ethereum." |
| `token_analytics` | Get detailed analytics for a token | `GET /tokens/:address/analytics` | "Show me analytics for the PEPE token." "What are the buy/sell volumes for USDT in the last 24 hours?" |

\* Premium Endpoint: To use the `token_search` API, you will need an API key associated with a Moralis account on the Business plan or a custom Enterprise plan.

## Configuration

The token skills require a Moralis API key to function. You can configure this in your agent's configuration file:

```yaml
skills:
  token:
    api_key: "your_moralis_api_key_here"
    states:
      token_price: "public"
      token_erc20_transfers: "public"
      token_search: "public"
      token_analytics: "public"
```

## Responses

All token skills return structured data from the Moralis API. Here are the typical response formats:

### Token Price

```json
{
  "tokenName": "Pepe",
  "tokenSymbol": "PEPE",
  "tokenLogo": "https://cdn.moralis.io/eth/0x6982508145454ce325ddbe47a25d4ec3d2311933.png",
  "tokenDecimals": "18",
  "usdPrice": 0.000012302426023896,
  "usdPriceFormatted": "0.000012302426023896",
  "24hrPercentChange": "-3.7369101031758394",
  "exchangeName": "Uniswap v3",
  "tokenAddress": "0x6982508145454ce325ddbe47a25d4ec3d2311933"
}
```

### Token Analytics

```json
{
  "tokenAddress": "0x6982508145454ce325ddbe47a25d4ec3d2311933",
  "totalBuyVolume": {
    "5m": "",
    "1h": 43678.642005116264,
    "6h": 129974.13379912674,
    "24h": 4583254.969119737
  },
  "totalSellVolume": {
    "5m": 147.69184595604904,
    "1h": 393.0296489666009,
    "6h": 257421.35479601548,
    "24h": 4735908.689740969
  },
  "totalBuyers": {
    "5m": "",
    "1h": 33,
    "6h": 115,
    "24h": 547
  },
  "totalSellers": {
    "5m": 1,
    "1h": 2,
    "6h": 78,
    "24h": 587
  }
}
```

## Usage Tips

- For the best performance, always specify the chain parameter when querying across multiple blockchains.
- When using the token_search endpoint, be aware of your Moralis plan limitations.
- The token analytics skill provides valuable trading data that can be used for token analysis and market assessment.

For more detailed information on each endpoint, refer to the [Moralis API documentation](https://docs.moralis.io/web3-data-api/evm). 