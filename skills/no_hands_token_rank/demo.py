from skill import get_wallet_rank

if __name__ == "__main__":
    wallet = input("Enter wallet address: ").strip()
    token_mint = input("Enter token mint address: ").strip()

    try:
        result = get_wallet_rank(wallet, token_mint)
        print("\n--- Token Holder Info ---")
        print(f"Wallet Address: {result['wallet_address']}")
        print(f"Wallet Rank: {result['wallet_rank']} out of {result['total_holders']}")
        print(f"Wallet Balance: {result['wallet_balance']} tokens")
        print(f"Top Holder: {result['top_holder']['address']}")
        print(f"Top Holder Amount: {result['top_holder']['amount']} tokens")
    except Exception as e:
        print(f"Error: {e}")
      
