# Goat SDK Integration

All GOAT Skills are supported by [GOAT](https://github.com/goat-sdk/goat/).

The list of supported tools can be found [here](https://github.com/goat-sdk/goat/tree/main/python#plugins).

## Sample configuration

```json
{
    "chains": {
        "base"
    }
}
```

## Sample Skills list

```json
{
    "inch1": {
        "api_key": "1inch api key string"
    },
    "coingecko": {
        "api_key": "coingecko api key string"
    },
    "allora": {
        "api_key": "allora api key string",
        "api_root": "https://api.upshot.xyz/v2/allora" 
    },
    "dexscreener": {},
    "erc20": {
        "tokens": [
            "goat_plugins.erc20.token.USDC"
        ]
    },
    "farcaster": {
        "api_key": "farcaster api key string",
        "base_url": "https://farcaster.xyz" 
    },
    "jsonrpc": {
        "endpoint": "https://eth.llamarpc.com"
    },
    "jupiter": {},
    "nansen": {
        "api_key": "nansen api key string"
    },
    "opensea": {
        "api_key": "opensea api key string"
    },
    "rugcheck": {
        "jwt_token": "rugcheck JWT token string"
    },
    "spl_token": {
        "network": "mainnet",
        "tokens": [
            "goat_plugins.erc20.token.USDC"
        ]
    },
    "superfluid": {},
    "uniswap": {
        "api_key": "uniswap api key string",
        "base_url": "https://app.uniswap.org" 
    }
}
```
