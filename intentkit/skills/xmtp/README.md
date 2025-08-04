# XMTP Skills

This skill category provides capabilities for creating XMTP protocol transaction requests that can be sent to users for signing.

## Features

- **xmtp_transfer**: Create ETH or ERC20 token transfer transactions on Base mainnet using XMTP protocol

## Key Innovations

This skill category uses a new response format mechanism:

- `response_format = "content_and_artifact"` in the base class
- Skills return a tuple `(content_message, List[ChatMessageAttachment])` instead of just a string
- The `content_message` is sent to the user as conversational text
- The `ChatMessageAttachment` list contains XMTP transaction data with type "xmtp"

## Requirements

- Agent must be configured for Base mainnet (`network_id: "base-mainnet"`)
- Agent must have an EVM wallet address configured
- Only supports Base mainnet (Chain ID: 8453)

## Supported Transfer Types

### ETH Transfers
- Direct ETH transfers using transaction value
- No token contract address required

### ERC20 Token Transfers
- Supports any ERC20 token on Base mainnet
- Uses `transfer(address,uint256)` function call
- Requires token contract address
- Automatically encodes function call data

## Transaction Format

### ETH Transfer Example
```json
{
  "version": "1.0",
  "from": "0x...",
  "chainId": "0x2105",
  "calls": [{
    "to": "0x...",
    "value": "0x16345785d8a0000",
    "data": "0x",
    "metadata": {
      "description": "Send 0.1 ETH to address",
      "transactionType": "transfer",
      "currency": "ETH",
      "amount": 100000000000000000,
      "decimals": 18,
      "toAddress": "0x..."
    }
  }]
}
```

### ERC20 Transfer Example
```json
{
  "version": "1.0",
  "from": "0x...",
  "chainId": "0x2105",
  "calls": [{
    "to": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "value": "0x0",
    "data": "0xa9059cbb000000000000000000000000...",
    "metadata": {
      "description": "Send 100 USDC to address",
      "transactionType": "erc20_transfer",
      "currency": "USDC",
      "amount": 100000000,
      "decimals": 6,
      "toAddress": "0x...",
      "tokenContract": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    }
  }]
}
```

## Parameters

- `from_address`: Sender's wallet address (must match agent's EVM wallet)
- `to_address`: Recipient's wallet address
- `amount`: Amount to transfer (in human-readable format, e.g., "1.5" for 1.5 tokens)
- `decimals`: Token decimals (18 for ETH, 6 for USDC, etc.)
- `currency`: Currency symbol ("ETH", "USDC", "DAI", etc.)
- `token_contract_address`: Token contract address (optional, leave empty for ETH)

## Usage

```python
# ETH Transfer:
# from_address: agent's EVM wallet
# to_address: recipient address
# amount: "0.1"
# decimals: 18
# currency: "ETH"
# token_contract_address: None

# USDC Transfer:
# from_address: agent's EVM wallet
# to_address: recipient address  
# amount: "100"
# decimals: 6
# currency: "USDC"
# token_contract_address: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
```