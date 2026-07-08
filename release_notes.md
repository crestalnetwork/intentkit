# Release v2.14.0

## New Features

- Networks now follow wallets. Each team wallet carries its own default network, editable on the wallet page (Safe and Privy smart wallets stay on the chain they were deployed on). On-chain tools automatically operate on the network of the wallet they are called with, so one agent can work across several chains through different wallets. The agent-level network setting has been removed.
- The agent create and edit forms are leaner: the model tuning parameters are gone, and all web3 toolsets are grouped under a collapsed "Advanced Settings" section that only appears when the team owns a wallet.

## Improvements

- Toolset rows in the agent form show a compact selected/total counter, and the toolset description expands together with the toolset.
- The wallet management API's rename endpoint became a general update endpoint covering the name and the default network, with validation of the allowed networks.
- Reduced redundant database lookups in the on-chain tool layer and fixed bugs in the OpenSea listing tools.
