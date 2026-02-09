# Release v0.10.0

## New Features

- **Gasless Batch Transactions**: Added support for batching multiple transactions into a single on-chain transaction for Safe wallets. When a master wallet is configured, transactions can be executed gaslessly (master wallet pays for gas).
- **LLM Models**: Added new LLM models to configuration

## Improvements

- Fixed lint issues across multiple modules
- Removed deprecated agent plugin data
- Removed some unused skills for cleaner codebase

Full Changelog: [v0.9.31...v0.10.0](https://github.com/crestalnetwork/intentkit/compare/v0.9.31...v0.10.0)