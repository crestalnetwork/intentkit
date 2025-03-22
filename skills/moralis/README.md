# Wallet Portfolio Skills

## Overview

The Wallet Portfolio Skills module provides comprehensive blockchain wallet analysis capabilities across EVM-compatible chains (Ethereum, BSC, Polygon, etc.) and Solana. This module integrates with Moralis API to fetch wallet balances, transaction history, NFT holdings, and more.

## Features

- Multi-chain portfolio analysis
- Token balances with USD values
- Transaction history with detailed metadata
- NFT holdings with metadata
- Solana-specific portfolio analysis
- Token approval monitoring

## Setup

1. Obtain a Moralis API key from [Moralis](https://moralis.io/)
2. Configure the module with your API key:

```json
{
  "api_key": "YOUR_MORALIS_API_KEY",
  "states": {
    "fetch_wallet_portfolio": "public",
    "fetch_chain_portfolio": "public",
    "fetch_nft_portfolio": "public",
    "fetch_transaction_history": "public",
    "fetch_solana_portfolio": "public"
  },
  "supported_chains": {
    "evm": true,
    "solana": true
  }
}
```

## Skills

### 1. Fetch Wallet Portfolio (`fetch_wallet_portfolio`)

Provides a comprehensive overview of a wallet's holdings across multiple chains.

#### Sample Prompts:

```
What's my portfolio value across all chains for address 0x742d35Cc6634C0532925a3b844Bc454e4438f44e?
```

```
Show me the total value of my crypto holdings for 0x742d35Cc6634C0532925a3b844Bc454e4438f44e across Ethereum and BSC
```

#### Example Response:

```
I've analyzed the wallet portfolio for address 0x742d35Cc6634C0532925a3b844Bc454e4438f44e across multiple chains.

Portfolio Summary:
- Total Net Worth: $12,567.82
- Ethereum: $8,934.21
- BSC: $2,456.78
- Polygon: $1,176.83

Top Holdings:
1. ETH (Ethereum): 1.53 ETH ($5,823.45)
2. USDT (Ethereum): 2,500.00 USDT ($2,500.00)
3. BNB (BSC): 4.25 BNB ($1,870.25)
4. MATIC (Polygon): 1,100.00 MATIC ($880.00)
5. AAVE (Ethereum): 3.45 AAVE ($610.76)

Would you like me to provide more details about any specific token or chain?
```

### 2. Fetch Chain Portfolio (`fetch_chain_portfolio`)

Provides detailed information about a wallet's holdings on a specific blockchain.

#### Sample Prompts:

```
What tokens do I have on Ethereum for address 0x742d35Cc6634C0532925a3b844Bc454e4438f44e?
```

```
Show me my token approvals on BSC for wallet 0x742d35Cc6634C0532925a3b844Bc454e4438f44e
```

#### Example Response:

```
I've analyzed your holdings on Ethereum (Chain ID: 1) for address 0x742d35Cc6634C0532925a3b844Bc454e4438f44e.

Portfolio on Ethereum:
- Total Value: $8,934.21

Native Token:
- ETH: 1.53 ETH ($5,823.45)

ERC-20 Tokens:
1. USDT: 2,500.00 USDT ($2,500.00)
2. AAVE: 3.45 AAVE ($610.76)
3. LINK: 0.01 LINK ($0.25)

Token Approvals:
1. USDT approved to Uniswap Router (0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D)
   - Unlimited approval (high risk)

2. AAVE approved to AAVE lending pool (0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9)
   - Amount: 10 AAVE
```

### 3. Fetch NFT Portfolio (`fetch_nft_portfolio`)

Retrieves NFT holdings for a wallet address across different chains.

#### Sample Prompts:

```
What NFTs do I own on address 0x742d35Cc6634C0532925a3b844Bc454e4438f44e?
```

```
Show me my Solana NFTs for wallet 5YNmS1R9nNSCDzb5a7mMJ1dwK9uHeAAF4CYuH1Oss2nS
```

#### Example Response:

```
I've found the following NFTs for address 0x742d35Cc6634C0532925a3b844Bc454e4438f44e:

Total NFTs: 7 (Ethereum: 4, Polygon: 3)

Ethereum NFTs:
1. CryptoPunk #8291
   - Collection: CryptoPunks
   - Token ID: 8291
   - Contract: 0xb47e3cd837dDF8e4c57F05d70Ab865de6e193BBB
   - Traits: Mohawk, Earring
   - Floor Price: 72.5 ETH

2. Bored Ape Yacht Club #2534
   - Collection: Bored Ape Yacht Club
   - Token ID: 2534
   - Contract: 0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D
   - Traits: Red Fur, 3D Glasses, Hat
   - Floor Price: 38.2 ETH

[2 more NFTs...]

Polygon NFTs:
1. Sandbox Land (-12, 40)
   - Collection: Sandbox
   - Token ID: 43215
   - Contract: 0x5CC5B05a8A13E3fBDB0BB9FcCd98D38e50F90c38
   
[2 more NFTs...]
```

### 4. Fetch Transaction History (`fetch_transaction_history`)

Retrieves detailed transaction history for a wallet address.

#### Sample Prompts:

```
Show me the recent transactions for 0x742d35Cc6634C0532925a3b844Bc454e4438f44e
```

```
What are my latest swaps on Ethereum for wallet 0x742d35Cc6634C0532925a3b844Bc454e4438f44e?
```

#### Example Response:

```
Here are the recent transactions for 0x742d35Cc6634C0532925a3b844Bc454e4438f44e on Ethereum:

1. Swap (2 hours ago)
   - Hash: 0x3a5e...f781
   - Swapped 1,000 USDT for 0.25 ETH on Uniswap
   - Fee: 0.005 ETH ($19.25)

2. Token Transfer (1 day ago)
   - Hash: 0x8f72...d4e3
   - Sent 50 LINK to 0x91B...5a4c
   - Fee: 0.002 ETH ($7.70)

3. NFT Purchase (2 days ago)
   - Hash: 0x6c9d...b2a1
   - Bought Bored Ape #2534 for 38.2 ETH
   - Fee: 0.012 ETH ($46.20)

4. Approval (3 days ago)
   - Hash: 0x2d7f...a9b3
   - Approved USDT for Uniswap Router
   - Fee: 0.003 ETH ($11.55)

5. Deposit (5 days ago)
   - Hash: 0x1e8c...f3d2
   - Received 2,000 USDT from Binance
   - Fee: N/A (you were the recipient)

Would you like to see more transactions or filter by a specific type?
```

### 5. Fetch Solana Portfolio (`fetch_solana_portfolio`)

Provides detailed information about a Solana wallet's holdings.

#### Sample Prompts:

```
What's in my Solana wallet 5YNmS1R9nNSCDzb5a7mMJ1dwK9uHeAAF4CYuH1Oss2nS?
```

```
Show me my SOL and SPL tokens for address 5YNmS1R9nNSCDzb5a7mMJ1dwK9uHeAAF4CYuH1Oss2nS
```

#### Example Response:

```
I've analyzed your Solana wallet (5YNmS1R9nNSCDzb5a7mMJ1dwK9uHeAAF4CYuH1Oss2nS):

Portfolio Summary:
- Total Value: $5,342.67

Native SOL:
- Balance: 25.8 SOL ($2,322.00)

SPL Tokens:
1. USDC: 1,500.00 USDC ($1,500.00)
2. RAY: 120.5 RAY ($960.78)
3. SRM: 300 SRM ($450.00)
4. MNGO: 4,500 MNGO ($45.00)
5. FIDA: 250 FIDA ($62.50)
6. STEP: 100 STEP ($2.40)

NFTs: 3 found (enable include_nfts parameter for details)

Associated Token Addresses:
- USDC: CK8a3uXCLZxmQZ9r7Q9eMEU9UKinLKzQi9VWNtmG9rB
- RAY: 7pbMGuVdG4rQt7QUjSYWQFEASVcS9eJtt7LUUVfZPsDR
[more addresses...]
```

## Advanced Usage

### Combining Skills

The wallet portfolio skills can be combined for comprehensive analysis. For example:

```
Can you analyze wallet 0x742d35Cc6634C0532925a3b844Bc454e4438f44e and show me:
1. Total portfolio value
2. NFT holdings
3. Recent transactions
```

### Response Example:

```
I've performed a comprehensive analysis of wallet 0x742d35Cc6634C0532925a3b844Bc454e4438f44e:

PORTFOLIO VALUE:
Total Net Worth: $12,567.82
- Ethereum: $8,934.21
- BSC: $2,456.78
- Polygon: $1,176.83

Top Holdings:
1. ETH (Ethereum): 1.53 ETH ($5,823.45)
2. USDT (Ethereum): 2,500.00 USDT ($2,500.00)
3. BNB (BSC): 4.25 BNB ($1,870.25)

NFT HOLDINGS:
Total NFTs: 7 (Ethereum: 4, Polygon: 3)

Notable NFTs:
1. CryptoPunk #8291 (Ethereum)
   - Floor Price: 72.5 ETH
2. Bored Ape Yacht Club #2534 (Ethereum)
   - Floor Price: 38.2 ETH
3. Sandbox Land (-12, 40) (Polygon)

RECENT TRANSACTIONS:
1. Swap (2 hours ago)
   - Swapped 1,000 USDT for 0.25 ETH on Uniswap
2. Token Transfer (1 day ago)
   - Sent 50 LINK to 0x91B...5a4c
3. NFT Purchase (2 days ago)
   - Bought Bored Ape #2534 for 38.2 ETH

Would you like me to focus on any specific aspect of this wallet?
```

## Error Handling

The skills handle various error conditions gracefully:

- Invalid addresses
- Unsupported chains
- API rate limiting
- Network issues

Each skill includes an `error` field in the response that will be populated with error information when applicable.

## Limitations

- Data is only as current as the Moralis API
- Some price data may not be available for smaller or newer tokens
- Transactions are limited to 100 per request by default
- NFT metadata and images may not be available for all NFTs
- Token approvals analysis may not identify all high-risk approvals

## Contributing

Contributions to improve the Wallet Portfolio Skills are welcome. Please ensure that your code follows the project's style and includes appropriate tests.