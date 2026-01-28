from typing import Any, Mapping

import httpx

from intentkit.skills.base import IntentKitSkill

JUPITER_QUOTE_API_URL = "https://api.jup.ag/swap/v1"
JUPITER_PRICE_API_URL = "https://api.jup.ag/price/v3"

COMMON_TOKENS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzcCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "WIF": "EKpQGSJtjMFqKZ9KQanSqErztviRPzJV8nDCZpQq8Yn9",
    "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
}


class JupiterBaseTool(IntentKitSkill):
    """Base class for Jupiter skills."""

    api_key: str | None = None

    def __init__(self, api_key: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key

    category: str = "jupiter"

    async def _make_request(
        self,
        endpoint: str,
        params: Mapping[str, Any] | None = None,
        api_type: str = "quote",
    ) -> dict[str, Any]:
        """Make a request to Jupiter API.

        Args:
            endpoint: The API endpoint path.
            params: Query parameters.
            api_type: "quote" or "price".

        Returns:
            JSON response.
        """
        base_url = (
            JUPITER_QUOTE_API_URL if api_type == "quote" else JUPITER_PRICE_API_URL
        )
        url = f"{base_url}{endpoint}"

        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url, params=params, headers=headers, timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                self.logger.error(f"Jupiter API error: {e}")
                raise RuntimeError(f"Jupiter API request failed: {e}")

    def _resolve_token_mint(self, symbol_or_mint: str) -> str:
        """Resolve a symbol to a mint address if possible, otherwise return as is."""
        upper_symbol = symbol_or_mint.upper()
        if upper_symbol in COMMON_TOKENS:
            return COMMON_TOKENS[upper_symbol]
        return symbol_or_mint
