"""ACP list products skill."""

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from .base import AcpBaseTool, acp_request, truncate_response, validate_url


class AcpListProductsInput(BaseModel):
    """Arguments for listing products from an ACP merchant."""

    merchant_url: str = Field(
        description="Base URL of the ACP merchant (e.g. https://merchant.example.com)"
    )
    timeout: float = Field(default=30.0, description="Timeout in seconds.")


class AcpListProducts(AcpBaseTool):
    """List available products from an ACP merchant."""

    name: str = "acp_list_products"
    description: str = (
        "List available products from an ACP merchant. "
        "Returns product IDs, names, descriptions, and prices in USDC."
    )
    args_schema: ArgsSchema | None = AcpListProductsInput

    @override
    async def _arun(
        self,
        merchant_url: str,
        timeout: float = 30.0,
        **_: Any,
    ) -> str:
        validate_url(merchant_url)
        url = f"{merchant_url.rstrip('/')}/products"
        response = await acp_request("GET", url, timeout=timeout)

        products = response.json()
        if not products:
            return "No products available."

        lines = ["Available products:"]
        for p in products:
            price_usd = p["price"] / 1_000_000
            lines.append(
                f"- {p['id']}: {p['name']} (${price_usd:.2f} USDC) - {p['description']}"
            )
        return truncate_response("\n".join(lines))
