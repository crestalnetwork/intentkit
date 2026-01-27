from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.jupiter.base import JupiterBaseTool


class JupiterGetPriceInput(BaseModel):
    ids: str = Field(
        description="Comma-separated list of token symbols or mint addresses (e.g., 'SOL,BONK' or 'So111...')."
    )


class JupiterGetPrice(JupiterBaseTool):
    name: str = "jupiter_get_price"
    description: str = (
        "Get the current price of Solana tokens in USD using Jupiter Price API."
    )
    args_schema: ArgsSchema | None = JupiterGetPriceInput

    async def _arun(
        self,
        ids: str,
        **kwargs,
    ) -> str:
        # Resolve IDs
        token_ids = [self._resolve_token_mint(t.strip()) for t in ids.split(",")]
        resolved_ids = ",".join(token_ids)

        params = {"ids": resolved_ids}

        try:
            data = await self._make_request("", params=params, api_type="price")
            # Response V3: {"So111...": {"id": "...", "type": "...", "usdPrice": "135.36"}, ...}
            # Note: V3 response is directly the map, or inside "data"?
            # User example: {"So111...": {...}} (Root object is the map)

            # However, standard Jupiter V3 docs sometimes show it wrapped.
            # Based on user output: {"So111...":{...}}
            # Let's handle both just in case, but prioritize root.

            result_data = data
            if (
                "data" in data
                and isinstance(data["data"], dict)
                and "So11111111111111111111111111111111111111112" not in data
            ):
                result_data = data["data"]

            # Format as Markdown Table
            table_header = "| Token | Price (USD) |\n| :--- | :--- |"
            table_rows = []

            for token_id, info in result_data.items():
                if not isinstance(info, dict):
                    continue

                price = info.get("usdPrice")

                # Try to map back mint to symbol for display
                display_name = token_id
                # Check for common tokens/symbols
                for sym, mint in self._get_common_tokens().items():
                    if mint == token_id:
                        display_name = sym
                        break

                # Truncate mint address if no symbol found
                if display_name == token_id:
                    display_name = f"`{token_id[:4]}...{token_id[-4:]}`"
                else:
                    display_name = f"**{display_name}**"

                if price is not None:
                    try:
                        price_float = float(price)
                        # Format nicely:
                        # > $1.00: 2 decimals
                        # < $1.00: up to 10 decimals (stripped)
                        if price_float >= 1.0:
                            price_str = f"${price_float:,.2f}"
                        else:
                            price_str = f"${price_float:.10f}".rstrip("0").rstrip(".")

                        table_rows.append(f"| {display_name} | {price_str} |")
                    except ValueError:
                        table_rows.append(f"| {display_name} | ${price} |")
                else:
                    table_rows.append(f"| {display_name} | *Not Found* |")

            if not table_rows:
                return f"No valid price data returned for {ids}."

            return "\n".join([table_header] + table_rows)

        except Exception as e:
            return f"Error fetching price: {e}"

    def _get_common_tokens(self) -> dict[str, str]:
        # Import here to avoid circular or just access base one?
        # Base class methods have access to global constants in that module?
        # Actually I can access intentkit.skills.jupiter.base.COMMON_TOKENS
        from intentkit.skills.jupiter.base import COMMON_TOKENS

        return COMMON_TOKENS
