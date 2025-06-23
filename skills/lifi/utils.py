"""
LiFi Skills Utilities

Common utilities and helper functions for LiFi token transfer skills.
"""

from typing import Any, Dict, List, Optional, Tuple

import httpx
from web3 import Web3

# Constants
LIFI_API_URL = "https://li.quest/v1"
DUMMY_ADDRESS = "0x552008c0f6870c2f77e5cC1d2eb9bdff03e30Ea0"  # For quotes

# Chain ID to name mapping (includes mainnet and testnet)
CHAIN_NAMES = {
    # Mainnet chains
    1: "Ethereum",
    10: "Optimism",
    56: "BNB Chain",
    100: "Gnosis Chain",
    137: "Polygon",
    250: "Fantom",
    8453: "Base",
    42161: "Arbitrum One",
    43114: "Avalanche",
    59144: "Linea",
    324: "zkSync Era",
    1101: "Polygon zkEVM",
    534352: "Scroll",
    # Testnet chains
    11155111: "Ethereum Sepolia",
    84532: "Base Sepolia",
    421614: "Arbitrum Sepolia",
    11155420: "Optimism Sepolia",
    80001: "Polygon Mumbai",
    5: "Ethereum Goerli",  # Legacy testnet
    420: "Optimism Goerli",  # Legacy testnet
}

# Standard ERC20 ABI for allowance and approve functions
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
]


def validate_inputs(
    from_chain: str,
    to_chain: str,
    from_token: str,
    to_token: str,
    from_amount: str,
    slippage: float,
    allowed_chains: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Validate all input parameters for LiFi operations.

    Returns:
        None if valid, error message string if invalid
    """
    # Validate slippage
    if slippage < 0.001 or slippage > 0.5:
        return "Invalid slippage: must be between 0.001 (0.1%) and 0.5 (50%)"

    # Validate chain identifiers can be converted to chain IDs
    try:
        convert_chain_to_id(from_chain)
    except ValueError as e:
        return f"Invalid source chain: {str(e)}"

    try:
        convert_chain_to_id(to_chain)
    except ValueError as e:
        return f"Invalid destination chain: {str(e)}"

    # Validate chains if restricted (use original chain names for restriction check)
    if allowed_chains:
        if from_chain not in allowed_chains:
            return f"Source chain '{from_chain}' is not allowed. Allowed chains: {', '.join(allowed_chains)}"
        if to_chain not in allowed_chains:
            return f"Destination chain '{to_chain}' is not allowed. Allowed chains: {', '.join(allowed_chains)}"

    # Validate amount is numeric and positive
    try:
        amount_float = float(from_amount)
        if amount_float <= 0:
            return "Amount must be greater than 0"
    except ValueError:
        return f"Invalid amount format: {from_amount}. Must be a numeric value."

    return None


def format_amount(amount: str, decimals: int) -> str:
    """
    Format amount from wei/smallest unit to human readable.

    Args:
        amount: Amount in smallest unit (wei/satoshi/etc)
        decimals: Number of decimal places for the token

    Returns:
        Formatted amount string
    """
    try:
        amount_int = int(amount)
        amount_float = amount_int / (10**decimals)

        # Format with appropriate precision
        if amount_float >= 1000:
            return f"{amount_float:,.2f}"
        elif amount_float >= 1:
            return f"{amount_float:.4f}"
        elif amount_float >= 0.01:
            return f"{amount_float:.6f}"
        else:
            return f"{amount_float:.8f}"
    except (ValueError, TypeError):
        return str(amount)


def get_chain_name(chain_id: int) -> str:
    """
    Get human readable chain name from chain ID.

    Args:
        chain_id: Blockchain chain ID

    Returns:
        Human readable chain name
    """
    return CHAIN_NAMES.get(chain_id, f"Chain {chain_id}")


def format_duration(duration: int) -> str:
    """
    Format duration in seconds to human readable format.

    Args:
        duration: Duration in seconds

    Returns:
        Formatted duration string
    """
    if duration < 60:
        return f"{duration} seconds"
    elif duration < 3600:
        return f"{duration // 60} minutes {duration % 60} seconds"
    else:
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        return f"{hours} hours {minutes} minutes"


def handle_api_response(
    response: httpx.Response,
    from_token: str,
    from_chain: str,
    to_token: str,
    to_chain: str,
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Handle LiFi API response and return data or error message.

    Args:
        response: HTTP response from LiFi API
        from_token, from_chain, to_token, to_chain: Transfer parameters for error messages

    Returns:
        Tuple of (data, error_message). One will be None.
    """
    if response.status_code == 400:
        try:
            error_data = response.json()
            error_message = error_data.get("message", response.text)
            return None, f"Invalid request: {error_message}"
        except (ValueError, TypeError, AttributeError):
            return None, f"Invalid request: {response.text}"
    elif response.status_code == 404:
        return (
            None,
            f"No route found for transfer from {from_token} on {from_chain} to {to_token} on {to_chain}. Try different tokens or chains.",
        )
    elif response.status_code != 200:
        return None, f"LiFi API error ({response.status_code}): {response.text}"

    try:
        data = response.json()
        if not isinstance(data, dict):
            return None, "Invalid response format from LiFi API."
        return data, None
    except Exception:
        return None, "Invalid response from LiFi API. Please try again."


def convert_chain_to_id(chain: str) -> int:
    """
    Convert chain identifier to numeric chain ID.

    Args:
        chain: Chain identifier (can be name, key, or numeric ID as string)

    Returns:
        Numeric chain ID

    Raises:
        ValueError: If chain identifier is not recognized
    """
    # If it's already a number, return it
    if chain.isdigit():
        return int(chain)

    # Chain name/key to ID mapping
    chain_mapping = {
        # Mainnet chains
        "ethereum": 1,
        "eth": 1,
        "1": 1,
        "optimism": 10,
        "opt": 10,
        "10": 10,
        "binance": 56,
        "bsc": 56,
        "bnb": 56,
        "56": 56,
        "gnosis": 100,
        "100": 100,
        "polygon": 137,
        "pol": 137,
        "matic": 137,
        "137": 137,
        "fantom": 250,
        "ftm": 250,
        "250": 250,
        "base": 8453,
        "base-mainnet": 8453,
        "8453": 8453,
        "arbitrum": 42161,
        "arb": 42161,
        "42161": 42161,
        "avalanche": 43114,
        "avax": 43114,
        "43114": 43114,
        "linea": 59144,
        "59144": 59144,
        "zksync": 324,
        "324": 324,
        "polygon-zkevm": 1101,
        "1101": 1101,
        "scroll": 534352,
        "534352": 534352,
        # Testnet chains
        "ethereum-sepolia": 11155111,
        "sepolia": 11155111,
        "11155111": 11155111,
        "base-sepolia": 84532,
        "84532": 84532,
        "arbitrum-sepolia": 421614,
        "421614": 421614,
        "optimism-sepolia": 11155420,
        "11155420": 11155420,
        "polygon-mumbai": 80001,
        "mumbai": 80001,
        "80001": 80001,
    }

    chain_lower = chain.lower()
    if chain_lower in chain_mapping:
        return chain_mapping[chain_lower]

    raise ValueError(f"Unsupported chain identifier: {chain}")


def convert_amount_to_wei(amount: str, token_symbol: str = "ETH") -> str:
    """
    Convert human-readable amount to wei format for LiFi API.

    Args:
        amount: Amount in human readable format (e.g., "0.0015")
        token_symbol: Token symbol to determine decimals

    Returns:
        Amount in wei format as string
    """
    # Default decimals for common tokens
    token_decimals = {
        "ETH": 18,
        "USDC": 6,
        "USDT": 6,
        "DAI": 18,
        "WETH": 18,
        "MATIC": 18,
        "BNB": 18,
        "AVAX": 18,
    }

    decimals = token_decimals.get(token_symbol.upper(), 18)

    try:
        # Convert string to float, then to wei
        amount_float = float(amount)
        amount_wei = int(amount_float * (10**decimals))
        return str(amount_wei)
    except (ValueError, TypeError):
        # If conversion fails, return original amount
        return amount


def build_quote_params(
    from_chain: str,
    to_chain: str,
    from_token: str,
    to_token: str,
    from_amount: str,
    slippage: float,
    from_address: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build parameters for LiFi quote API request.

    Args:
        from_chain, to_chain, from_token, to_token, from_amount: Transfer parameters
        slippage: Slippage tolerance
        from_address: Wallet address (uses dummy if None)

    Returns:
        Dictionary of API parameters

    Raises:
        ValueError: If chain identifiers are not recognized
    """
    # Convert amount to wei format for API
    wei_amount = convert_amount_to_wei(from_amount, from_token)

    return {
        "fromChain": convert_chain_to_id(from_chain),
        "toChain": convert_chain_to_id(to_chain),
        "fromToken": from_token,
        "toToken": to_token,
        "fromAmount": wei_amount,
        "fromAddress": from_address or DUMMY_ADDRESS,
        "slippage": slippage,
    }


def is_native_token(token_address: str) -> bool:
    """
    Check if token address represents a native token (ETH, MATIC, etc).

    Args:
        token_address: Token contract address

    Returns:
        True if native token, False if ERC20
    """
    return (
        token_address == "0x0000000000000000000000000000000000000000"
        or token_address == ""
        or token_address.lower() == "0x0"
    )


def prepare_transaction_params(transaction_request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare transaction parameters for CDP wallet provider.

    Args:
        transaction_request: Transaction request from LiFi API

    Returns:
        Formatted transaction parameters

    Raises:
        Exception: If required parameters are missing
    """
    to_address = transaction_request.get("to")
    value = transaction_request.get("value", "0")
    data = transaction_request.get("data", "0x")

    if not to_address:
        raise Exception("No destination address in transaction request")

    # Convert value to integer if it's a string
    if isinstance(value, str):
        value = int(value, 16) if value.startswith("0x") else int(value)

    return {
        "to": Web3.to_checksum_address(to_address),
        "value": value,
        "data": data,
    }


def format_quote_basic_info(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and format basic quote information.

    Args:
        data: Quote response from LiFi API

    Returns:
        Dictionary with formatted basic info
    """
    action = data.get("action", {})
    estimate = data.get("estimate", {})

    from_token_info = action.get("fromToken", {})
    to_token_info = action.get("toToken", {})

    from_amount = action.get("fromAmount", "0")
    to_amount = estimate.get("toAmount", "0")
    to_amount_min = estimate.get("toAmountMin", "0")

    from_token_decimals = from_token_info.get("decimals", 18)
    to_token_decimals = to_token_info.get("decimals", 18)

    return {
        "from_token": from_token_info.get("symbol", "Unknown"),
        "to_token": to_token_info.get("symbol", "Unknown"),
        "from_chain": get_chain_name(action.get("fromChainId")),
        "to_chain": get_chain_name(action.get("toChainId")),
        "from_amount": format_amount(from_amount, from_token_decimals),
        "to_amount": format_amount(to_amount, to_token_decimals),
        "to_amount_min": format_amount(to_amount_min, to_token_decimals),
        "tool": data.get("tool", "Unknown"),
        "from_amount_usd": estimate.get("fromAmountUSD"),
        "to_amount_usd": estimate.get("toAmountUSD"),
        "execution_duration": estimate.get("executionDuration"),
    }


def format_fees_and_gas(data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Format fee and gas cost information from quote data.

    Args:
        data: Quote response from LiFi API

    Returns:
        Tuple of (fees_text, gas_text)
    """
    estimate = data.get("estimate", {})

    # Extract gas and fee costs
    gas_costs = estimate.get("gasCosts", [])
    fee_costs = []

    # Collect fee information from included steps
    for step in data.get("includedSteps", []):
        step_fees = step.get("estimate", {}).get("feeCosts", [])
        if step_fees:
            fee_costs.extend(step_fees)

    # Format fees
    fees_text = ""
    if fee_costs:
        fees_text = "**Fees:**\n"
        total_fee_usd = 0
        for fee in fee_costs:
            fee_name = fee.get("name", "Unknown fee")
            fee_amount = fee.get("amount", "0")
            fee_token = fee.get("token", {}).get("symbol", "")
            fee_decimals = fee.get("token", {}).get("decimals", 18)
            fee_percentage = fee.get("percentage", "0")
            fee_usd = fee.get("amountUSD", "0")

            fee_amount_formatted = format_amount(fee_amount, fee_decimals)
            percentage_str = (
                f" ({float(fee_percentage) * 100:.3f}%)"
                if fee_percentage != "0"
                else ""
            )
            fees_text += (
                f"- {fee_name}: {fee_amount_formatted} {fee_token}{percentage_str}"
            )

            if fee_usd and float(fee_usd) > 0:
                fees_text += f" (${fee_usd})"
                total_fee_usd += float(fee_usd)

            fees_text += "\n"

        if total_fee_usd > 0:
            fees_text += f"- **Total Fees:** ~${total_fee_usd:.4f}\n"

    # Format gas costs
    gas_text = ""
    if gas_costs:
        gas_text = "**Gas Cost:**\n"
        total_gas_usd = 0
        for gas in gas_costs:
            gas_amount = gas.get("amount", "0")
            gas_token = gas.get("token", {}).get("symbol", "ETH")
            gas_decimals = gas.get("token", {}).get("decimals", 18)
            gas_usd = gas.get("amountUSD", "0")
            gas_type = gas.get("type", "SEND")

            gas_amount_formatted = format_amount(gas_amount, gas_decimals)
            gas_text += f"- {gas_type}: {gas_amount_formatted} {gas_token}"

            if gas_usd and float(gas_usd) > 0:
                gas_text += f" (${gas_usd})"
                total_gas_usd += float(gas_usd)

            gas_text += "\n"

        if total_gas_usd > 0:
            gas_text += f"- **Total Gas:** ~${total_gas_usd:.4f}\n"

    return fees_text, gas_text


def format_route_info(data: Dict[str, Any]) -> str:
    """
    Format routing information from quote data.

    Args:
        data: Quote response from LiFi API

    Returns:
        Formatted route information text
    """
    included_steps = data.get("includedSteps", [])
    if len(included_steps) <= 1:
        return ""

    route_text = "**Route:**\n"
    for i, step in enumerate(included_steps, 1):
        step_tool = step.get("tool", "Unknown")
        step_type = step.get("type", "unknown")
        route_text += f"{i}. {step_tool} ({step_type})\n"

    return route_text


def create_erc20_approve_data(spender_address: str, amount: str) -> str:
    """
    Create encoded data for ERC20 approve function call.

    Args:
        spender_address: Address to approve
        amount: Amount to approve

    Returns:
        Encoded function call data
    """
    contract = Web3().eth.contract(
        address=Web3.to_checksum_address("0x0000000000000000000000000000000000000000"),
        abi=ERC20_ABI,
    )
    return contract.encode_abi("approve", [spender_address, int(amount)])


def get_api_error_message(response: httpx.Response) -> str:
    """
    Extract error message from API response.

    Args:
        response: HTTP response

    Returns:
        Formatted error message
    """
    try:
        error_data = response.json()
        return error_data.get("message", response.text)
    except (ValueError, TypeError, AttributeError):
        return response.text


def get_explorer_url(chain_id: int, tx_hash: str) -> str:
    """
    Generate blockchain explorer URL for a transaction.

    Args:
        chain_id: Blockchain chain ID
        tx_hash: Transaction hash

    Returns:
        Explorer URL for the transaction
    """
    # Explorer URLs for different chains
    explorers = {
        1: "https://etherscan.io/tx/",  # Ethereum
        10: "https://optimistic.etherscan.io/tx/",  # Optimism
        56: "https://bscscan.com/tx/",  # BSC
        100: "https://gnosisscan.io/tx/",  # Gnosis
        137: "https://polygonscan.com/tx/",  # Polygon
        250: "https://ftmscan.com/tx/",  # Fantom
        8453: "https://basescan.org/tx/",  # Base
        42161: "https://arbiscan.io/tx/",  # Arbitrum
        43114: "https://snowtrace.io/tx/",  # Avalanche
        59144: "https://lineascan.build/tx/",  # Linea
        324: "https://explorer.zksync.io/tx/",  # zkSync Era
        1101: "https://zkevm.polygonscan.com/tx/",  # Polygon zkEVM
        534352: "https://scrollscan.com/tx/",  # Scroll
        # Testnet explorers
        11155111: "https://sepolia.etherscan.io/tx/",  # Ethereum Sepolia
        84532: "https://sepolia.basescan.org/tx/",  # Base Sepolia
        421614: "https://sepolia.arbiscan.io/tx/",  # Arbitrum Sepolia
        11155420: "https://sepolia-optimism.etherscan.io/tx/",  # Optimism Sepolia
        80001: "https://mumbai.polygonscan.com/tx/",  # Polygon Mumbai
    }

    base_url = explorers.get(chain_id, "https://etherscan.io/tx/")
    return f"{base_url}{tx_hash}"


def format_transaction_result(
    tx_hash: str, chain_id: int, token_info: dict = None
) -> str:
    """
    Format transaction result with explorer link.

    Args:
        tx_hash: Transaction hash
        chain_id: Chain ID where transaction was executed
        token_info: Optional token information for context

    Returns:
        Formatted transaction result message
    """
    explorer_url = get_explorer_url(chain_id, tx_hash)
    chain_name = get_chain_name(chain_id)

    result = "Transaction successful!\n"
    result += f"Transaction Hash: {tx_hash}\n"
    result += f"Network: {chain_name}\n"
    result += f"Explorer: {explorer_url}\n"

    if token_info:
        result += f"Token: {token_info.get('symbol', 'Unknown')}\n"
        result += f"Amount: {token_info.get('amount', 'Unknown')}\n"

    return result
