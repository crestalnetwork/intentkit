## CDP AgentKit

All CDP Skills are supported by [AgentKit](https://github.com/coinbase/cdp-agentkit/).

AgentKit supports the following tools:

### Wallet Management
- `get_wallet_details` - Get detailed information about your MPC Wallet, including the wallet's address and current network.

- `get_balance` - Query token balances for specific assets in your wallet. Supports querying balances for any token using its asset ID (e.g., "eth", "usdc") or contract address.

- `request_faucet_funds` - Request test tokens from the [Base Sepolia faucet](https://portal.cdp.coinbase.com/products/faucet). Useful for testing and development on testnet.

- `address_reputation` - Check the reputation and risk assessment of any Ethereum address. Helps evaluate the trustworthiness of addresses you interact with.

### Asset Operations
- `transfer` - Transfer tokens between addresses. Features:
  - Supports any ERC20 token or native asset (ETH)
  - Accepts amount in standard units (e.g., "15", "0.000001")
  - Destination can be an address, ENS name (example.eth), or Basename (example.base.eth)
  - Supports gasless transfers for USDC on Base networks (base-sepolia and base-mainnet)

- `trade` - Execute token trades on supported DEXs (mainnet networks only). Allows trading between any supported assets by specifying:
  - Amount to trade
  - Source asset ID (e.g., "eth", "usdc", or contract address)
  - Target asset ID
  
- `wrap_eth` - Convert ETH to WETH (Wrapped Ether) for DeFi compatibility. WETH is the ERC20 token version of ETH required by many DeFi protocols.

### Token Management
- `deploy_token` - Deploy custom [ERC-20](https://www.coinbase.com/learn/crypto-glossary/what-is-erc-20) token contracts. Specify:
  - Token name
  - Symbol
  - Total supply
  The deploying wallet becomes the owner and initial token holder.

- `deploy_contract` - Deploy any smart contract with custom bytecode and constructor arguments. Provides full flexibility for deploying any type of contract.

### NFT Operations
- `get_balance_nft` - Query NFT balances for specific collections. Check ownership of NFTs in any ERC721 contract.

- `mint_nft` - Mint NFTs from existing contracts. Useful for participating in NFT drops or creating new tokens in your own collections.

- `deploy_nft` - Deploy new NFT (ERC-721) contracts with customizable parameters:
  - Collection name
  - Symbol
  - Base URI for token metadata

- `transfer_nft` - Transfer NFTs between addresses. Supports:
  - Any ERC721 contract
  - Transfer by token ID
  - Custom source address
  - Destination can be address, ENS, or Basename

### Base Name Service
- `register_basename` - Register a [Basename](https://www.base.org/names) for your wallet address. Basenames are human-readable identifiers for your wallet on Base network (e.g., "example.base.eth").

### Zora Wow Integration
- `wow_create_token` - Deploy a token using [Zora's Wow Launcher](https://wow.xyz/mechanics) with bonding curve (Base only). Specify:
  - Token name
  - Symbol
  - Optional IPFS metadata URI

- `wow_buy_token` - Buy [Zora Wow](https://wow.xyz/) ERC-20 memecoins with ETH (Base only). Purchase tokens from existing Wow contracts.

- `wow_sell_token` - Sell [Zora Wow](https://wow.xyz/) ERC-20 memecoins for ETH (Base only). Specify:
  - Contract address
  - Amount in wei (1 wei = 0.000000000000000001 tokens)

### Superfluid Integration
- `superfluid_create_flow` - Create a continuous token streaming flow. Set up recurring payments by specifying:
  - Recipient address
  - Token address
  - Flow rate (tokens per second in wei)

- `superfluid_update_flow` - Modify an existing token streaming flow. Adjust the flow rate of ongoing streams.

- `superfluid_delete_flow` - Stop and delete an existing token streaming flow. Terminate ongoing payment streams.

### Morpho Integration
- `morpho_deposit` - Deposit assets into Morpho's yield-generating vaults. Earn yield on your deposited tokens.

- `morpho_withdraw` - Withdraw assets from Morpho's yield-generating vaults. Access your deposited funds and earned yield.

### Pyth Network Integration
- `pyth_fetch_price` - Get real-time price data from Pyth Network oracles. Access accurate price feeds for various assets.

- `pyth_fetch_price_feed_id` - Retrieve price feed IDs for Pyth Network price feeds. Required for accessing specific price data streams.

Any action not supported by default by AgentKit can be added by [adding agent capabilities](https://docs.cdp.coinbase.com/agentkit/docs/add-agent-capabilities).

AgentKit supports every network that the [CDP SDK supports](https://docs.cdp.coinbase.com/cdp-apis/docs/networks).
