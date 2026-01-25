import asyncio
import os

from dotenv import load_dotenv
from eth_account import Account
from web3 import AsyncWeb3

# Load environment variables (to get intentkit config if needed, or just assume .env)
load_dotenv()

# Base Sepolia RPC
RPC_URL = "https://sepolia.base.org"


async def main():
    # Read bytecode
    with open("allowance_module_creation.txt", "r") as f:
        bytecode = f.read().strip()

    if not bytecode.startswith("0x"):
        bytecode = "0x" + bytecode

    # Get private key
    # Try to get from env or intentkit config (simulated here)
    private_key = os.getenv("MASTER_WALLET_PRIVATE_KEY")
    if not private_key:
        print("Error: MASTER_WALLET_PRIVATE_KEY not found in env")
        return

    w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(RPC_URL))
    account = Account.from_key(private_key)
    address = account.address
    print(f"Deploying from {address}")

    nonce = await w3.eth.get_transaction_count(address)
    gas_price = await w3.eth.gas_price

    tx = {
        "from": address,
        "to": None,
        "data": bytecode,
        "nonce": nonce,
        "gas": 5000000,
        "gasPrice": gas_price,
        "chainId": 84532,
    }

    print("Signing transaction...")
    signed = w3.eth.account.sign_transaction(tx, private_key)

    print("Sending transaction...")
    try:
        tx_hash = await w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"Transaction sent: {tx_hash.hex()}")

        print("Waiting for receipt...")
        receipt = await w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"Receipt status: {receipt['status']}")

        if receipt["status"] == 1:
            print(f"Deployment SUCCESS! Contract Address: {receipt['contractAddress']}")
        else:
            print(f"Deployment FAILED! Receipt: {dict(receipt)}")
    except Exception as e:
        print(f"Error sending transaction: {e}")


if __name__ == "__main__":
    asyncio.run(main())
