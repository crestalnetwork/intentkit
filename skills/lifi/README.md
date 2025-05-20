# LiFi Token Transfer Skills

This module provides two skills for token transfers using the [LiFi protocol](https://li.fi):

1. **Token Quote** - Get quotes for token transfers without execution
2. **Token Execute** - Execute actual token transfers (requires CDP wallet)

## Features

- Get quotes for token transfers across different blockchains
- Get quotes for token swaps on the same blockchain
- Execute actual token transfers using the agent's CDP wallet
- View estimated fees, gas costs, and slippage
- See the routing path of the transfer

> **IMPORTANT:** A properly configured CDP wallet is **required** for the `token_execute` skill.
> The `token_quote` skill works without a CDP wallet.

## Configuration

To enable the LiFi skills in your agent configuration:

```yaml
id: my-agent
skills:
  lifi:
    enabled: true
    states: 
      token_quote: public  # can be public, private, or disabled
      token_execute: private  # can be public, private, or disabled
    # Optional configuration parameters
    default_slippage: 0.03  # 3% slippage tolerance
    allowed_chains: ["ETH", "POL", "ARB"]  # Limit to specific chains (optional)
    max_execution_time: 300  # Maximum execution time in seconds for token_execute
```

The agent **must** have a CDP wallet configured to use the `token_execute` skill. See the [CDP Wallet Requirements](#cdp-wallet-requirements) section for details.

## CDP Wallet Requirements

To use the `token_execute` skill, your agent must have:

1. A properly configured CDP wallet with `cdp_wallet_data` set
2. Sufficient funds for the transfer amount and gas fees
3. Network configuration that matches the chains you intend to use

Example agent configuration with CDP wallet:

```yaml
id: my-agent
wallet_provider: "cdp"
cdp_network_id: "ethereum-mainnet"  # Set to the network you want to use
# The system needs to have CDP credentials configured
```

### Setting Up the CDP Wallet

1. In your agent settings, ensure `wallet_provider` is set to `"cdp"` 
2. Set the `cdp_network_id` to the blockchain network you want to use
3. Ensure your agent has been initialized with the appropriate CDP wallet credentials

## Troubleshooting

### Missing CDP Wallet Configuration

If you see an error like:
```
AttributeError: 'NoneType' object has no attribute 'cdp_wallet_data'
```

This indicates that:
1. Your agent doesn't have CDP wallet configuration properly set up
2. You're trying to use the `token_execute` skill which requires the wallet

Solutions:
- Use the `token_quote` skill instead which doesn't require a CDP wallet
- Configure your agent with a proper CDP wallet (see [CDP Wallet Requirements](#cdp-wallet-requirements))
- Check that your system has CDP API keys properly configured

Note: When using the quote-only skill, the system uses a dummy address 
`0x552008c0f6870c2f77e5cC1d2eb9bdff03e30Ea0` to request quotes from the LiFi API. This 
allows getting accurate price information without requiring a real wallet.

### API Errors

Common LiFi API errors:

- **400 Bad Request - "Token not supported"**: The token symbol or address you provided is not recognized on the specified chain.
- **404 Not Found - "No Route Found"**: There's no available path to complete the requested transfer. Try different tokens or chains.

### Other Common Issues

- **Insufficient funds**: Ensure your CDP wallet has enough tokens for the transfer and gas fees
- **Chain not supported**: Verify that the chains you're using are supported by LiFi
- **Slippage too low**: If transactions are failing, try increasing the slippage tolerance

## Usage

### Token Quote Skill

Use the `token_quote` skill to get information about rates, fees, and execution paths without performing actual transfers.

#### Example Interactions for Token Quote:

- "Get a quote for transferring 1 USDC from Gnosis to Polygon"
- "What's the rate for swapping 0.1 ETH to USDC on Ethereum?"
- "Check the fees for sending DAI to USDT on Arbitrum"
- "How much MATIC would I get if I transfer 10 USDC from Ethereum to Polygon?"

#### Parameters for Token Quote:

- `from_chain`: The source chain (e.g., 'ETH', 'POL', 'ARB', 'DAI')
- `to_chain`: The destination chain (e.g., 'ETH', 'POL', 'ARB', 'DAI')
- `from_token`: The token to send (e.g., 'USDC', 'ETH', 'DAI')
- `to_token`: The token to receive (e.g., 'USDC', 'ETH', 'DAI')
- `from_amount`: The amount to send including all decimals (e.g., '1000000' for 1 USDC with 6 decimals)
- `slippage`: The maximum allowed slippage for the transaction (0.03 represents 3%)

### Token Execute Skill

Use the `token_execute` skill to perform actual token transfers using the agent's CDP wallet.

#### Example Interactions for Token Execute:

- "Execute a transfer of 1 USDC from Gnosis to Polygon"
- "Swap 0.1 ETH for USDC on Ethereum"
- "Transfer 5 USDC from Ethereum to Optimism"

#### Parameters for Token Execute:

- `from_chain`: The source chain (e.g., 'ETH', 'POL', 'ARB', 'DAI')
- `to_chain`: The destination chain (e.g., 'ETH', 'POL', 'ARB', 'DAI')
- `from_token`: The token to send (e.g., 'USDC', 'ETH', 'DAI')
- `to_token`: The token to receive (e.g., 'USDC', 'ETH', 'DAI')
- `from_amount`: The amount to send including all decimals (e.g., '1000000' for 1 USDC with 6 decimals)
- `slippage`: The maximum allowed slippage for the transaction (0.03 represents 3%)

## How It Works

### Token Quote

The `token_quote` skill:
1. Makes a request to the LiFi API for quote information
2. Formats the response into readable information including:
   - Token amounts and conversion rates
   - Estimated fees and gas costs
   - USD value equivalents
   - Execution time estimates
   - Transaction routing path

### Token Execute

The `token_execute` skill:
1. Retrieves a quote from the LiFi API
2. Checks and sets token allowances if needed (for ERC20 tokens)
3. Executes the transfer using the agent's CDP wallet
4. Monitors the transaction status
5. Returns the transaction hash, status, and detailed information

## Advanced Configuration

### Default Slippage

You can set a default slippage tolerance for all transfers in the agent configuration:

```yaml
skills:
  lifi:
    default_slippage: 0.03  # 3% slippage tolerance
```

This value will be used if no slippage parameter is provided when calling the skills.

### Allowed Chains

You can restrict which chains the agent can use for transfers:

```yaml
skills:
  lifi:
    allowed_chains: ["ETH", "POL", "ARB", "OPT"]
```

If this option is not set, all chains supported by LiFi can be used.

### Maximum Execution Time

You can set a maximum time to wait for transaction confirmation when using the `token_execute` skill:

```yaml
skills:
  lifi:
    max_execution_time: 300  # 5 minutes
```

## Example Usage Flow

1. User: "What would I get if I swap 0.1 ETH for USDC on Ethereum?"
2. Agent: [Uses token_quote to get and show the transfer details]
3. User: "That looks good, please execute the transfer"
4. Agent: [Uses token_execute to perform the actual transfer]
5. Agent: [Returns transaction hash and status information]

## Notes

The `token_execute` skill requires sufficient funds in the agent's CDP wallet. Before using this skill, ensure that:

1. Your agent has a properly configured CDP wallet
2. The wallet has sufficient funds for the transfer and gas fees
3. The wallet has the appropriate permissions on the source chain

This skill can be used alongside other CDP-related skills to provide a complete token management solution for your agent. 