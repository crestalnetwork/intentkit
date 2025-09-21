# Coinbase Developer Platform

## CDP AgentKit

All CDP Skills are supported by [AgentKit](https://github.com/coinbase/agentkit/).

The core CDP skills bundle now focuses on wallet management and faucet access. Available tools are:

```
WalletActionProvider_get_balance
WalletActionProvider_get_wallet_details
WalletActionProvider_native_transfer
CdpApiActionProvider_request_faucet_funds
CdpEvmWalletActionProvider_get_swap_price
CdpEvmWalletActionProvider_swap
```

Other AgentKit providers such as Basename, ERC20, ERC721, Morpho, Pyth, Superfluid, WETH, and WOW are exposed through their own dedicated skill categories under `intentkit/skills/`.
