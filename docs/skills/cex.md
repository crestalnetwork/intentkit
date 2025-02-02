"""
# CEX Skills Documentation

CEX skills are first-class skills designed for interacting with centralized cryptocurrency exchanges like OKX. 

## Using the trade_on_okx Skill

1. Configure your OKX API credentials in the Agent model.
2. Use the `trade_on_okx` skill to automatically trade cryptocurrencies based on technical indicators.
3. Input Parameters:
    - `symbol`: The trading pair (e.g., BTC/USDT).
    - `timeframe`: The timeframe for the analysis (e.g., 1h).
    - `amount`: The amount to trade.

## Example

```python
from skills.cex.okx import TradeOnOkx

trade_skill = TradeOnOkx(api_key, secret, password)
trade_skill.run("BTC/USDT", timeframe="1h", amount=0.001)
```

"""