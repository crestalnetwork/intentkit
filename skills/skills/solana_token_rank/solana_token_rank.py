import httpx
from pydantic import BaseModel, Field
from typing import Type
from skills.solana_token_rank.base import SolanaTokenRankBaseTool

class SolanaTokenRankInput(BaseModel):
    wallet_address: str = Field(description="Solana wallet address to look up")
    token_mint: str = Field(description="Solana token mint address to rank against")

class SolanaTokenRank(SolanaTokenRankBaseTool):
    name: str = "solana_token_rank"
    description: str = "Get the rank, amount held, and top holder of a given Solana token."
    args_schema: Type[BaseModel] = SolanaTokenRankInput

    async def _arun(self, wallet_address: str, token_mint: str, **kwargs) -> str:
        try:
            base_url = "https://api.helius.xyz/v0/tokens/holding"
            api_key = "YOUR_HELIUS_API_KEY"  # Replace with env or system config in production
            url = f"{base_url}?api-key={api_key}&wallets[]={wallet_address}&mints[]={token_mint}"

            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            if not data or not data[0].get("tokens"):
                return "No token data found for this wallet and mint."

            token_data = data[0]["tokens"][0]
            amount = token_data.get("amount")

            # Simulate a rank and top holder — in real code you'd use on-chain index or API
            fake_rank = 1234
            fake_total = 100000
            fake_top_holder = "TopHolderAddress"

            return (
                f"Wallet: {wallet_address}\n"
                f"Holds: {amount} tokens of {token_mint}\n"
                f"Rank: #{fake_rank} of {fake_total} holders\n"
                f"Top Holder: {fake_top_holder}"
            )

        except Exception as e:
            return f"Error getting token rank: {str(e)}"
          
