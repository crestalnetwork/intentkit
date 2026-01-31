# Coinbase Developer Platform

## CDP SDK

IntentKit CDP skills are implemented with the official [CDP SDK](https://github.com/coinbase/cdp-sdk) and use the unified wallet interface inside IntentKit.

The core CDP skills bundle focuses on wallet management and native transfers. Available tools are:

```
cdp_get_balance
cdp_get_wallet_details
cdp_native_transfer
```

Other on-chain providers such as Basename, ERC20, ERC721, Morpho, Pyth, Superfluid, WETH, and WOW are exposed through their own dedicated skill categories under `intentkit/skills/`.