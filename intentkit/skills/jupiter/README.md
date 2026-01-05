# 🪐 Jupiter Skill (IntentKit)

> **"The best prices on Solana."**

This skill integrates **Jupiter Aggregator** into IntentKit, enabling AI agents to check token prices and fetch best-route swap quotes directly from the Solana blockchain.

## ✨ Features

- **Real-Time Prices**: Fetch live token prices in USD (via Jupiter Price API v3).
- **Smart Quotes**: Get the best swap routes across liquidity sources (via Jupiter Swap API v1).
- **Rich Output**: Responses are formatted in clean Markdown for easy readability.

---

## 🛠️ Configuration

To use this skill, you need a **Jupiter API Key** (for higher rate limits & stability).
Get one at: [Jupiter Developer Portal](https://portal.jup.ag/).

### 1. Enable in Agent Config

Add `jupiter` to your agent's skill list in your config file:

```yaml
skills:
  - name: jupiter
    config:
      enabled: true
      api_key: "your_api_key_here" # 1. Paste Key Here
      states:
        jupiter_get_price: public
        jupiter_get_quote: public
```

### 2. Environment Variable (Alternative)

You can also set the key via environment variable:

```bash
export JUPITER_API_KEY="your_api_key_here"
```

---

## 🤖 Available Tools

### 1. `jupiter_get_price`

Checks the current USD price of any Solana token.

**Inputs:**

- `ids`: Token symbol (e.g., `SOL`, `BONK`) or Mint Address. Can be comma-separated.

**Example Agent Output:**

| Token    | Price (USD) |
| :------- | :---------- |
| **SOL**  | $135.27     |
| **BONK** | $0.00001168 |

---

### 2. `jupiter_get_quote`

Finds the best route to swap tokens.

**Inputs:**

- `input_mint`: Token to sell (Mint Address or Symbol).
- `output_mint`: Token to buy.
- `amount`: Exact amount in **atomic units** (e.g., `1000000000` = 1 SOL).
- `slippage_bps`: Slippage tolerance (default `50` = 0.5%).

**Example Agent Output:**

### 🪐 Jupiter Swap Quote

- **Swap**: 1,000,000,000 **SOL** ➡️ 135,271,877 **USDC**
- **Price Impact**: `0.01%`
- **Slippage**: 0.5%

> _Note: This is a quote only. No transaction was signed._

---

## 📦 Developer Info

- **Skill Path**: `intentkit/skills/jupiter/`
- **APIs Used**:
  - Price V3: `https://api.jup.ag/price/v3`
  - Swap V1: `https://api.jup.ag/swap/v1`
