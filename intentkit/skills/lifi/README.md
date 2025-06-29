# LiFi Skills
Cross-chain token transfers and swaps using the LiFi protocol with CDP wallet integration.

## Features

- **Token Quotes**: Get real-time quotes for token swaps and cross-chain transfers
- **Token Execution**: Execute token swaps and transfers with automatic transaction handling
- **Explorer URLs**: Get direct blockchain explorer links for all transactions
- **Multi-chain Support**: Works with 15+ blockchains including Base, Ethereum, Arbitrum, Polygon
- **Testnet Support**: Full support for testnet operations (Base Sepolia, Ethereum Sepolia, etc.)

## Skills Available

1. **`token_quote`** - Get quotes for token transfers (public access)
2. **`lifi_token_execute`** - Execute token transfers (requires CDP wallet)

## Test Prompts

Use these exact prompts to test the LiFi skills:

### 1. Check Wallet Address
```
what is my wallet address
```

### 2. Check Balances
```
tell me my balance in eth and usdc
```

### 3. Get Quote for Token Swap
```
now get me quote to swap my usdc to eth on the same chain that is base mainnet
```

### 4. Execute Token Swap
```
yes do the swap now
```

### 5. Verify Transaction
```
tell me my balance in eth and usdc
```

## Expected Results

### Quote Response
```
### Token Transfer Quote

**From:** 2.2019 USDC on Base
**To:** 0.00100259 ETH on Base
**Minimum Received:** 0.00097251 ETH
**Bridge/Exchange:** sushiswap

**Value:** $2.2017 → $2.2067
**Estimated Time:** 30 seconds

**Gas Cost:**
- SEND: 0.00001005 ETH ($0.0221)
- **Total Gas:** ~$0.0221
```

### Execution Response
```
**Token Swap Executed Successfully**

Transaction successful!
Transaction Hash: 0xe7d026c7598699909794df9f7858e48cc56c03e4d428f5cc62f51c1979617fd1
Network: Base
Explorer: https://basescan.org/tx/0xe7d026c7598699909794df9f7858e48cc56c03e4d428f5cc62f51c1979617fd1
Token: USDC → ETH
Amount: 2.2019

**Status:** Completed (same-chain swap)
```

## Supported Chains

**Mainnet**: Ethereum, Base, Arbitrum, Optimism, Polygon, Avalanche, Fantom, BSC, Linea, zkSync Era, Scroll

**Testnet**: Ethereum Sepolia, Base Sepolia, Arbitrum Sepolia, Optimism Sepolia, Polygon Mumbai

## Prerequisites

- CDP wallet configured and funded
- Agent with LiFi skills enabled
- Sufficient token balance for swaps/transfers
- Network gas tokens for transaction fees

## Configuration

The skills are automatically configured with:
- Default slippage: 3%
- Maximum execution time: 300 seconds
- Support for all major tokens (ETH, USDC, USDT, DAI, WETH, etc.)

## Error Handling

The skills handle common errors automatically:
- Invalid chain identifiers
- Insufficient balances
- Network connectivity issues
- Transaction failures with detailed error messages

### CDP Wallet Requirements

To use the `token_execute` skill, your agent must have:

1. **CDP Wallet Configuration**: A properly configured CDP wallet with `cdp_wallet_data` set
2. **Sufficient Funds**: Enough tokens for the transfer amount plus gas fees
3. **Network Configuration**: Proper network settings matching your intended chains


## Usage Examples

### Token Quote Examples

#### Cross-Chain Transfer Quote
```
"Get a quote for transferring 100 USDC from Ethereum to Polygon"
```

#### Same-Chain Swap Quote
```
"What's the rate for swapping 0.5 ETH to USDC on Ethereum?"
```

#### Fee Analysis
```
"Check the fees for sending 1000 DAI from Arbitrum to Base"
```

#### Amount Calculation
```
"How much MATIC would I get if I transfer 50 USDC from Ethereum to Polygon?"
```

### Token Execute Examples

#### Execute Cross-Chain Transfer
```
"Execute a transfer of 100 USDC from Ethereum to Polygon"
```

#### Execute Same-Chain Swap
```
"Swap 0.1 ETH for USDC on Base"
```

#### Execute with Custom Slippage
```
"Transfer 500 DAI from Arbitrum to Optimism with 1% slippage"
```

## Supported Networks

### Major Networks
- **Ethereum** (ETH) - Chain ID: 1
- **Polygon** (POL) - Chain ID: 137  
- **Arbitrum One** (ARB) - Chain ID: 42161
- **Optimism** (OPT) - Chain ID: 10
- **Base** (BASE) - Chain ID: 8453
- **BNB Chain** (BSC) - Chain ID: 56
- **Avalanche** (AVAX) - Chain ID: 43114
- **Gnosis Chain** (DAI) - Chain ID: 100

### Layer 2 Networks
- **Linea** - Chain ID: 59144
- **zkSync Era** - Chain ID: 324
- **Polygon zkEVM** - Chain ID: 1101
- **Scroll** - Chain ID: 534352

## How It Works

### Token Quote Process

1. **Validates** input parameters (chains, tokens, amounts, slippage)
2. **Queries** LiFi API for the best route and pricing
3. **Formats** comprehensive quote information including:
   - Token amounts and conversion rates
   - Detailed fee breakdown (LP fees, bridge fees, etc.)
   - Gas cost estimates in native tokens and USD
   - Execution time estimates
   - Routing path through bridges/exchanges
   - USD value equivalents

### Token Execute Process

1. **Gets Quote** - Retrieves routing and pricing information
2. **Checks Wallet** - Validates CDP wallet configuration and funds
3. **Sets Approval** - Automatically approves ERC20 tokens if needed
4. **Executes Transaction** - Sends the transfer transaction
5. **Monitors Status** - Tracks cross-chain transfer completion
6. **Reports Results** - Provides transaction hash and final status

## Troubleshooting

### Common Issues

#### "CDP client not available"
**Problem**: Agent doesn't have CDP wallet configuration
**Solution**: 
- Set `wallet_provider: "cdp"` in agent configuration
- Ensure CDP credentials are properly configured
- Use `token_quote` for research without requiring a wallet

#### "No route found"
**Problem**: LiFi cannot find a path for the requested transfer
**Solutions**:
- Try different token pairs
- Use more liquid tokens (USDC, ETH, etc.)
- Check if both chains support the requested tokens
- Reduce transfer amount if liquidity is limited

#### "Invalid request: Token not supported"
**Problem**: Token symbol or address not recognized
**Solutions**:
- Use popular token symbols (USDC, ETH, DAI, MATIC)
- Verify token exists on the source chain
- Use full token contract address instead of symbol

#### "Failed to approve token"
**Problem**: ERC20 token approval failed
**Solutions**:
- Ensure wallet has enough native tokens for gas
- Check if token contract allows approvals
- Try again with a smaller amount

#### "Transfer pending" (taking too long)
**Problem**: Cross-chain transfer is slow
**Solutions**:
- Wait longer (some bridges take 10-30 minutes)
- Check the explorer link for detailed status
- Contact LiFi support if transfer is stuck

### Configuration Issues

#### Invalid Slippage
```
Error: "Invalid slippage: must be between 0.001 (0.1%) and 0.5 (50%)"
```
**Solution**: Use slippage between 0.1% and 50% (e.g., 0.03 for 3%)

#### Chain Restrictions
```
Error: "Source chain 'ETH' is not allowed"
```
**Solution**: Update `allowed_chains` in configuration or remove the restriction

#### Execution Timeout
```
Status: "Still pending - transfer may take longer to complete"
```
**Solution**: Increase `max_execution_time` or wait for manual completion

## Best Practices

### For Token Quotes
- Use quotes to compare different routes before executing
- Check gas costs and fees before large transfers
- Consider execution time for time-sensitive operations

### For Token Execution  
- Always get a quote first to understand costs
- Ensure sufficient gas tokens in your wallet
- Use appropriate slippage (1-3% for stable pairs, 3-5% for volatile pairs)
- Monitor large transfers using the explorer link

### For Production Use
- Set reasonable `allowed_chains` to prevent unexpected transfers
- Use `private` state for execution skills in production
- Monitor transfer status for cross-chain operations
- Keep some native tokens for gas in each chain you use

## API Reference

### Token Quote Parameters
- `from_chain`: Source blockchain (string)
- `to_chain`: Destination blockchain (string)  
- `from_token`: Token to send (symbol or address)
- `to_token`: Token to receive (symbol or address)
- `from_amount`: Amount in smallest unit (string)
- `slippage`: Slippage tolerance 0.001-0.5 (float, optional)

### Token Execute Parameters
Same as Token Quote - the skill handles the execution automatically.

### Response Format

**Quote Response**: Detailed markdown with transfer details, fees, gas costs, and routing information.

**Execute Response**: Transaction hash, status monitoring, and complete transfer summary.
