#!/usr/bin/env python3
"""Simple example script for account.list_token_balances using CDP client.

This script demonstrates how to:
1. Create a CDP client with API credentials
2. Import an existing wallet account using the wallet secret
3. List token balances for the account on base network

Usage:
    uv run scripts/cdp_list_token_balances_example.py

Environment variables required:
    CDP_API_KEY_ID: Your CDP API key ID
    CDP_API_KEY_SECRET: Your CDP API key secret
    CDP_WALLET_SECRET: Your CDP wallet secret (base64 encoded)
"""

import asyncio
import os

from cdp import CdpClient
from dotenv import load_dotenv

load_dotenv()


async def main():
    """Main function to demonstrate account.list_token_balances."""
    # Get credentials from environment variables
    api_key_id = os.getenv("CDP_API_KEY_ID")
    api_key_secret = os.getenv("CDP_API_KEY_SECRET")
    wallet_secret = os.getenv("CDP_WALLET_SECRET")

    if not all([api_key_id, api_key_secret, wallet_secret]):
        print("Error: Missing required environment variables:")
        print("- CDP_API_KEY_ID")
        print("- CDP_API_KEY_SECRET")
        print("- CDP_WALLET_SECRET")
        return

    print("Creating CDP client...")
    cdp_client = CdpClient(
        api_key_id=api_key_id,
        api_key_secret=api_key_secret,
        wallet_secret=wallet_secret,
    )

    account = await cdp_client.evm.get_account(name="eva")

    print(f"load account with address: {account.address}")

    # if client close too early, it will have error
    # await cdp_client.close()

    # List token balances on base network
    print("\nListing token balances on base network...")
    token_balances = await account.list_token_balances("base")
    print(token_balances)

    await cdp_client.close()


if __name__ == "__main__":
    asyncio.run(main())
