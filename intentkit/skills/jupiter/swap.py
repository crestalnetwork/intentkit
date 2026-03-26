from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.jupiter.base import COMMON_TOKENS, JupiterBaseTool


class JupiterGetQuoteInput(BaseModel):
    input_mint: str = Field(description="Token to swap FROM (symbol or mint address)")
    output_mint: str = Field(description="Token to swap TO (symbol or mint address)")
    amount: int = Field(description="Amount in atomic units")
    slippage_bps: int = Field(default=50, description="Slippage in basis points")


class JupiterGetQuote(JupiterBaseTool):
    name: str = "jupiter_get_quote"
    description: str = "Get a swap quote from Jupiter. Returns best route and estimated output. Does NOT execute."
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

            in_amt = data.get("inAmount", "0")
            out_amt = data.get("outAmount", "0")
            price_impact = data.get("priceImpactPct")

            # Format nicely
            in_amount_disp = f"{int(in_amt):,}"
            out_amount_disp = f"{int(out_amt):,}"

            # Map mints to symbols if possible
            in_token_name = input_mint
            out_token_name = output_mint

            for sym, mint in COMMON_TOKENS.items():
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
            raise ToolException(f"Error fetching quote: {e}")
