import httpx
from typing import Type
from pydantic import BaseModel, Field
from skills.solana_token.base import SolanaTokenBaseSkill
from langchain_core.runnables import RunnableConfig

class SolanaTokenRankInput(BaseModel):
    wallet_address: str = Field(description="The Solana wallet address")
    token_mint: str = Field(description="The token mint address to check")

class SolanaTokenRank(SolanaTokenBaseSkill):
    name: str = "solana_token_rank"
    description: str = "Get wallet rank, token amount held, and top holder of a token on Solana using Helius."
    args_schema: Type[BaseModel] = SolanaTokenRankInput

    async def _arun(
        self,
        config: RunnableConfig,
        wallet_address: str,
        token_mint: str,
        **kwargs
    ) -> str:
        context = self.context_from_config(config)
        api_key = context.config.get("helius_api_key")

        if not api_key:
            return "Missing Helius API key in config."

        url = f"https://api.helius.xyz/v1/token-holders?api-key={api_key}&mint={token_mint}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            return f"Failed to fetch token holders: {str(e)}"

        holders = data.get("holders", [])
        sorted_holders = sorted(holders, key=lambda h: float(h["amount"]), reverse=True)

        wallet_rank = next((i + 1 for i, h in enumerate(sorted_holders) if h["owner"] == wallet_address), None)
        wallet_amount = next((h["amount"] for h in sorted_holders if h["owner"] == wallet_address), "0")
        top_holder = sorted_holders[0] if sorted_holders else {}

        return {
            "wallet_rank": wallet_rank or "Not Found",
            "wallet_amount": wallet_amount,
            "top_holder": {
                "address": top_holder.get("owner", "N/A"),
                "amount": top_holder.get("amount", "N/A")
            },
            "total_holders": len(sorted_holders)
        }
      
