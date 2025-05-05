# DappLooker Skill

This skill provides access to the DappLooker API for retrieving comprehensive data and analytics for AI agent tokens.

## Features

The DappLooker skill allows your agent to:

- Retrieve detailed AI agent token market data using token tickers or contract addresses
- Get real-time price information, market cap, and volume
- Access technical indicators like support/resistance levels and RSI
- View token holder insights including distribution and concentration metrics
- Monitor smart money movements and developer wallet activity
- Check supply information and token fundamentals

## Key Data Points Available

According to the [DappLooker documentation](https://docs.dapplooker.com/data-apis-for-ai/overview), the API provides:

### Token & Market Data
- **Token Metrics**: Price, volume, market cap, and liquidity
- **Technical Indicators**: Support/resistance levels, RSI, SMA, and more
- **Circulating & Burned Supply**: Information about inflation, scarcity, and value impact

### Agent-Level Intelligence
- **Agent Mindshare**: Measures visibility and traction across the ecosystem
- **Confidence Score**: Evaluates project credibility, contract safety, and risks
- **Historical Context**: Deployment details, contract origin, and dev history

### Smart Money & Whale Flows
- **Smart Netflows**: Token movements among top wallets (inflows vs. outflows)
- **Whale Concentration**: Wallet clustering and impact analysis
- **Top Holder Map**: Visual bubble distribution for wallet-wise token dominance

### Holder Wallets Activity
- **Wallets Tracking**: Number of linked wallets per protocol & holdings
- **Token Holder Insights**: Token holder behavior, first 100 buyers data, including snipers
- **Wallet Funding & Txns**: Inflow/outflow monitoring of developer-related transactions

### Risk Management Analysis
- **Rug Scanner**: Flags potential risks with agents investment
- **Project Health Alerts**: Alerts for centralized token ownership and other risks

## Important Note

**This skill is specifically designed for AI agent tokens.** It may not return data for general cryptocurrencies like BTC, ETH, SOL, etc. DappLooker specializes in providing detailed analytics for AI-focused crypto projects.

## Configuration

To use this skill, you'll need to:

1. Enable the skill in your agent configuration
2. Obtain a DappLooker API key from [DappLooker](https://docs.dapplooker.com/dapplooker-ai/ai-apis)
3. Configure the skill in your agent settings

### Agent Configuration

```yaml
skills:
  dapplooker:
    enabled: true
    api_key: "your_dapplooker_api_key"  # Optional if using environment variable
    states:
      dapplooker_token_data: public  # or "private" for agent owner only
```

### Environment Variable

You can also set the DappLooker API key as an environment variable:

```
DAPPLOOKER_API_KEY=your_dapplooker_api_key
```

The skill will first check the agent configuration for the API key, and if not found, it will use the environment variable.

## Usage

Your agent can now access AI agent token data by using the `dapplooker_token_data` skill:

- Query by token ticker (e.g., "aixbt,vader") 
- Query by contract address (e.g., "0x4F9Fd6Be4a90f2620860d680c0d4d5Fb53d1A825")
- Specify blockchain network (default is "base")

## Example

A user might ask:
"What's the current price and market metrics for AIXBT token on Base?"

The agent would use the DappLooker skill to retrieve and present this information in a structured format.

If a user asks about non-AI agent tokens like Bitcoin or Ethereum, the skill will inform them that DappLooker specializes in AI agent tokens and suggest querying for AI-focused projects instead. 