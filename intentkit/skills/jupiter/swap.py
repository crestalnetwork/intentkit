from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.jupiter.base import JupiterBaseTool


class JupiterGetQuoteInput(BaseModel):
    input_mint: str = Field(
        description="The Mint Address of the token to swap FROM. (e.g., 'So111...' or 'SOL')"
    )
    output_mint: str = Field(
        description="The Mint Address of the token to swap TO. (e.g., 'EPj...' or 'USDC')"
    )
    amount: int = Field(
        description="The amount to swap in atomic units (e.g., 1000000000 for 1 SOL)."
    )
    slippage_bps: int = Field(
        default=50,
        description="Slippage tolerance in basis points. 50 = 0.5%.",
    )


class JupiterGetQuote(JupiterBaseTool):
    name: str = "jupiter_get_quote"
    description: str = (
        "Get a swap quote from Jupiter Aggregator V6. "
        "Returns the best route and estimated output amount. "
        "Does NOT execute the swap."
    )
    args_schema: ArgsSchema | None = JupiterGetQuoteInput

    async def _arun(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,
        **kwargs,
    ) -> str:
        # Resolve Map
        resolved_input = self._resolve_token_mint(input_mint)
        resolved_output = self._resolve_token_mint(output_mint)

        params = {
            "inputMint": resolved_input,
            "outputMint": resolved_output,
            "amount": str(amount),
            "slippageBps": str(slippage_bps),
        }

        try:
            data = await self._make_request("/quote", params=params, api_type="quote")
            # Format
            # Keys: inputMint, inAmount, outAmount, priceImpactPct, routePlan

            in_amt = data.get("inAmount")
            out_amt = data.get("outAmount")
            price_impact = data.get("priceImpactPct")

            # Format nicely
            in_amount_disp = f"{int(in_amt):,}"
            out_amount_disp = f"{int(out_amt):,}"

            # Map mints to symbols if possible
            in_token_name = input_mint
            out_token_name = output_mint

            for sym, mint in self._get_common_tokens().items():
                if mint == input_mint:
                    in_token_name = sym
                if mint == output_mint:
                    out_token_name = sym

            if in_token_name == input_mint:
                in_token_name = f"`{input_mint[:4]}...`"
            if out_token_name == output_mint:
                out_token_name = f"`{output_mint[:4]}...`"

            return (
                f"### 🪐 Jupiter Swap Quote\n\n"
                f"- **Swap**: {in_amount_disp} **{in_token_name}** ➡️ {out_amount_disp} **{out_token_name}**\n"
                f"- **Price Impact**: `{price_impact}%`\n"
                f"- **Slippage**: {slippage_bps / 100}%\n"
                f"\n> *Note: This is a quote only. No transaction was signed.*"
            )

        except Exception as e:
            return f"Error fetching quote: {e}"
