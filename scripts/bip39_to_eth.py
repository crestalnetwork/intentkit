from bip32 import BIP32
from eth_keys.datatypes import PrivateKey
from eth_utils import to_checksum_address


def bip39_seed_to_eth_keys(seed_hex):
    """
    Converts a BIP39 seed to an Ethereum private key, public key, and address.
    """
    # Convert the hex seed to bytes
    seed_bytes = bytes.fromhex(seed_hex)

    # Derive the master key from the seed
    bip32 = BIP32.from_seed(seed_bytes)

    # Derive the Ethereum address using the standard derivation path
    private_key_bytes = bip32.get_privkey_from_path("m/44'/60'/0'/0/0")

    # Create a private key object
    private_key = PrivateKey(private_key_bytes)

    # Get the public key
    public_key = private_key.public_key

    # Get the Ethereum address
    address = public_key.to_address()

    return {
        "private_key": private_key.to_hex(),
        "public_key": public_key.to_hex(),
        "address": to_checksum_address(address),
    }


if __name__ == "__main__":
    # Your testing seed
    seed_hex = "ad915af6edcb5818c5eeebbdb081106fbfda38a46fd92693aab4b21d4616d24310f5827564528594eca0fd059147a70d6a4ff599fac1a7772442e074a1caf3bf"

    keys = bip39_seed_to_eth_keys(seed_hex)

    print(f"Private Key: {keys['private_key']}")
    print(f"Public Key: {keys['public_key']}")
    print(f"Wallet Address: {keys['address']}")

    # Verification
    expected_address = "0x2E31f87E0f5Ac1B887fe4BdB131c605F903aDA96"
    print(f"\nVerification successful: {keys['address'] == expected_address}")
