# Wallet Portfolio & Blockchain Analysis Skills

## Overview

The Wallet Portfolio & Blockchain Analysis Skills module provides comprehensive blockchain wallet analysis and transaction exploration capabilities across EVM-compatible chains (Ethereum, BSC, Polygon, etc.) and Solana. This module integrates with Moralis API to fetch wallet balances, transaction data, block information, NFT holdings, and more.

## Features

- Multi-chain portfolio analysis
- Token balances with USD values
- Transaction history with detailed metadata
- Transaction exploration and decoding
- Block data retrieval and analysis
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
    "fetch_solana_portfolio": "public",
    "fetch_transaction_by_hash": "public",
    "fetch_latest_block": "public",
    "fetch_block_by_hash_or_number": "public",
    "fetch_block_by_date": "public"
  },
  "supported_chains": {
    "evm": true,
    "solana": true
  }
}
```

## Wallet Portfolio Skills

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

Retrieves detailed transaction history for a wallet address with enhanced analytics.

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

Transaction Statistics:
- Total Transactions: 156
- Swaps: 42
- Transfers: 87
- Approvals: 12
- Other: 15

Recent Activity:
1. Swap (2 hours ago)
   - Hash: 0x3a5e...f781
   - Swapped 1,000 USDT for 0.25 ETH on Uniswap
   - Fee: 0.005 ETH ($19.25)
   - Function: swap(uint256,uint256,address[],address)

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

## Blockchain Data Skills

### 6. Fetch Transaction By Hash (`fetch_transaction_by_hash`)

Retrieves detailed information about a specific transaction by its hash.

#### Sample Prompts:

```
Show me details for transaction 0xfeda0e8f0d6e54112c28d319c0d303c065d1125c9197bd653682f5fcb0a6c81e
```

```
What happened in this transaction: 0x1ed85b3757a6d31d01a4d6677fc52fd3911d649a0af21fe5ca3f886b153773ed?
```

#### Example Response:

```
Transaction 0x1ed85b3757a6d31d01a4d6677fc52fd3911d649a0af21fe5ca3f886b153773ed
Status: Success
Type: Transfer
From: 0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0 (Binance 1)
To: 0x003dde3494f30d861d063232c6a8c04394b686ff (Binance 2)
Value: 0.115580 ETH
Block: 12386788
Timestamp: 2021-05-07T11:08:35.000Z

This transaction was a simple ETH transfer between two addresses. The transaction was successful and used 21,000 gas at a price of 52.5 Gwei, resulting in a fee of 0.0011025 ETH.

The transaction occurred on the Ethereum mainnet and did not involve any smart contract interactions or token transfers.
```

### 7. Fetch Latest Block (`fetch_latest_block`)

Retrieves the latest block number from a blockchain network.

#### Sample Prompts:

```
What's the latest block on Ethereum?
```

```
Show me the current block height for BSC
```

#### Example Response:

```
The latest block on Ethereum (Chain ID: 1) is 18243567.

This block was mined approximately 12 seconds ago.
```

### 8. Fetch Block By Hash or Number (`fetch_block_by_hash_or_number`)

Retrieves detailed information about a block by its hash or number.

#### Sample Prompts:

```
Show me block 17000000 on Ethereum
```

```
Get details for block 0x9b559aef7ea858608c2e554246fe4a24287e7aeeb976848df2b9a2531f4b9171
```

#### Example Response:

```
Block #17000000 on Ethereum (Chain ID: 1)

Block Details:
- Hash: 0x2241c2a0926e7c876af6c0bb355461fe5ef7a682fa0441125575fa5c5af5fe90
- Timestamp: 2023-06-13T10:42:15.000Z
- Miner: 0xea674fdde714fd979de3edf0f56aa9716b898ec8
- Gas Used: 29,892,458 (99.87% of gas limit)
- Size: 142,157 bytes
- Transactions: 318

This block contains 318 transactions and was mined by Ethermine (0xea674fdde714fd979de3edf0f56aa9716b898ec8). The total gas used was 29,892,458, which is 99.87% of the block's gas limit.
```

### 9. Fetch Block By Date (`fetch_block_by_date`)

Retrieves block information based on a specific date.

#### Sample Prompts:

```
What block was mined on June 15, 2023 on Ethereum?
```

```
Show me the blockchain state on 2023-01-01
```

#### Example Response:

```
On June 15, 2023, block #17034268 was mined on Ethereum (Chain ID: 1).

Block Details:
- Hash: 0x3a33181831a3d5c23072378163e43179743f79f8921c2a07e23da3c953502742
- Timestamp: 2023-06-15T00:00:12.000Z
- Miner: 0xea674fdde714fd979de3edf0f56aa9716b898ec8
- Gas Used: 29,956,842 (99.86% of gas limit)
- Size: 143,965 bytes
- Transactions: 327

This block was mined by Ethermine (0xea674fdde714fd979de3edf0f56aa9716b898ec8) at the beginning of June 15, 2023.
```

## Advanced Usage

### Combining Skills

The wallet portfolio and blockchain data skills can be combined for comprehensive analysis. For example:

```
Can you analyze wallet 0x742d35Cc6634C0532925a3b844Bc454e4438f44e and show me:
1. Total portfolio value
2. NFT holdings
3. Recent transactions and decode the last swap transaction
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
Most recent swap transaction (3 hours ago):
- Hash: 0x3a5e...f781
- Function: swapExactTokensForETH(uint256,uint256,address[],address,uint256)
- Parameters:
  - amountIn: 1000000000 (uint256) - 1,000 USDT with 6 decimals
  - amountOutMin: 249158750524475790 (uint256) - Minimum 0.249 ETH expected
  - path: ["0xdAC17F958D2ee523a2206206994597C13D831ec7","0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"] - USDT to WETH path
  - to: "0x742d35Cc6634C0532925a3b844Bc454e4438f44e" - Your address
  - deadline: 1689542498 (uint256) - Transaction deadline timestamp

The transaction successfully swapped 1,000 USDT for 0.25 ETH using Uniswap Router.

Would you like me to focus on any specific aspect of this wallet?
```

### Transaction Analysis

The transaction analysis skills can provide deep insights into on-chain activity:

```
Can you analyze this transaction 0xfeda0e8f0d6e54112c28d319c0d303c065d1125c9197bd653682f5fcb0a6c81e and explain what happened in simple terms?
```

### Response Example:

```
I've analyzed transaction 0xfeda0e8f0d6e54112c28d319c0d303c065d1125c9197bd653682f5fcb0a6c81e:

TRANSACTION SUMMARY:
This was an interaction with the Uniswap V2 Router on Ethereum, executed on May 7, 2021.

WHAT HAPPENED:
In simple terms, someone swapped approximately 5,000 USDT for 1.89 ETH using Uniswap.

DETAILS:
- Type: Token Swap (DEX)
- Platform: Uniswap V2
- Function Called: swapExactTokensForETH
- Tokens Involved:
  * Sent: 5,000 USDT
  * Received: 1.89 ETH
- Fee Paid: 0.0084 ETH (approximately $21.50 at that time)
- Result: Successful

This transaction represents a typical decentralized exchange swap where USDT stablecoin was exchanged for ETH. The transaction was initiated by a wallet associated with Binance and executed through the Uniswap V2 protocol.
```

## Error Handling

The skills handle various error conditions gracefully:

- Invalid addresses
- Unsupported chains
- API rate limiting
- Network issues
- Malformed transaction hashes
- Non-existent blocks

Each skill includes an `error` field in the response that will be populated with error information when applicable.

## Limitations

- Data is only as current as the Moralis API
- Some price data may not be available for smaller or newer tokens
- Transactions are limited to 100 per request by default
- NFT metadata and images may not be available for all NFTs
- Token approvals analysis may not identify all high-risk approvals
- Transaction decoding depends on verified ABIs in the Moralis database
- Block data for very old blocks may be slower to retrieve

## Contributing

Contributions to improve the Wallet Portfolio & Blockchain Analysis Skills are welcome. Please ensure that your code follows the project's style and includes appropriate tests.