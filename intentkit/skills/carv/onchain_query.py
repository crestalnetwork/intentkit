import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Literal, Type

from pydantic import BaseModel, Field

from intentkit.skills.carv.base import CarvBaseTool

logger = logging.getLogger(__name__)


class CarvInput(BaseModel):
    """
    Input schema for CARV SQL Query API.
    Defines parameters controllable by the user when invoking the tool.
    """

    question: str = Field(
        ...,
        description="The question to query on-chain data.",
    )
    chain: Literal["ethereum", "base", "bitcoin", "solana"] = Field(
        ...,
        description="supported chain is ethereum, base, bitcoin, solana",
    )


class OnchainQueryTool(CarvBaseTool):
    """
    Tool for querying on-chain data using natural language via the CARV SQL Query API.

    This tool allows you to ask questions about blockchain data in plain English, and it will return
    the relevant information. Behind the scenes, it uses the CARV API to convert your question into a SQL query
    and retrieve the results.

    Supported Blockchains: Ethereum, Base, Bitcoin, and Solana.

    If the question is about a blockchain other than the ones listed above, or is not a clear question, the
    tool will return an error.
    """

    name: str = "carv_onchain_query"
    description: str = (
        "Query blockchain data from Ethereum, Base, Bitcoin, or Solana using natural language. "
        "This tool provides access to detailed metrics including block information (timestamps, hashes, miners, gas used/limits), "
        "transaction details (hashes, sender/receiver addresses, amounts, gas prices), and overall network utilization. "
        "It supports aggregate analytics such as daily transaction counts, average gas prices, top wallet activity, and blockchain growth trends. "
        "You can filter results by time range, address type, transaction value, and other parameters.\n\n"
        "IMPORTANT Rules:\n"
        "- Only Ethereum, Base, Bitcoin, and Solana are supported.\n"
        "- Always infer the target blockchain from the user's query.\n"
        "- If an unsupported blockchain is requested, clearly explain the limitation.\n"
        "- Convert user input into a specific and actionable natural language query (e.g., "
        '"What\'s the most active address on Ethereum over the past 24 hours?" or '
        '"Show the largest ETH transaction in the last 30 days").\n'
        "- Respond in clear, concise natural language using only the data returned by the tool.\n"
        "- Avoid markdown or bullet points unless explicitly requested.\n"
        "- ETH values are denominated in 18 decimals—consider 10^18 when interpreting amounts.\n"
        "- Never fabricate or infer data beyond what the tool provides."
    )
    args_schema: Type[BaseModel] = CarvInput

    async def _arun(
        self,
        question: str,
        chain: str,  # type: ignore
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Queries the CARV SQL Query API and returns the response.
        """
        context = self.get_context()
        try:
            await self.apply_rate_limit(context)

            payload = {"question": question}

            result, error = await self._call_carv_api(
                context=context,
                endpoint="/ai-agent-backend/sql_query_by_llm",
                method="POST",
                payload=payload,
            )

            if error is not None or result is None:
                logger.error(f"Error returned from CARV API: {error}")
                return {
                    "error": True,
                    "error_type": "APIError",
                    "message": "Failed to fetch data from CARV API.",
                    "details": error,
                }

            _normalize_unit(result, chain)
            return {"success": True, **result}

        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
            return {
                "error": True,
                "error_type": type(e).__name__,
                "message": "An unexpected error occurred.",
                "details": str(e),
            }


def _normalize_unit(response_data: Dict[str, Any], chain: str) -> None:
    """
    Normalizes the 'value' field in on-chain response data to a human-readable format.
    Adds the corresponding token ticker after the value.

    Supported chains:
    - Ethereum: 10^18 -> ETH
    - Base: 10^18 -> ETH
    - Solana: 10^9 -> SOL
    - Bitcoin: 10^8 -> BTC
    """
    column_infos = response_data.get("column_infos", [])
    rows = response_data.get("rows", [])

    if "value" not in column_infos:
        return

    value_index = column_infos.index("value")

    chain = chain.lower()
    if chain == "ethereum":
        divisor = Decimal("1e18")
        ticker = "ETH"
    elif chain == "base":
        divisor = Decimal("1e18")
        ticker = "ETH"
    elif chain == "solana":
        divisor = Decimal("1e9")
        ticker = "SOL"
    elif chain == "bitcoin":
        divisor = Decimal("1e8")
        ticker = "BTC"
    else:
        logger.warning(f"Unsupported chain '{chain}' for unit normalization.")
        return

    for row in rows:
        items = row.get("items", [])
        if len(items) > value_index:
            original_value = items[value_index]
            try:
                normalized = str(original_value).strip()
                try:
                    value_decimal = Decimal(normalized)
                except InvalidOperation:
                    value_decimal = Decimal.from_float(float(normalized))

                converted = value_decimal / divisor
                formatted_value = (
                    format(converted, "f").rstrip("0").rstrip(".")
                    if "." in format(converted, "f")
                    else format(converted, "f")
                )
                items[value_index] = f"{formatted_value} {ticker}"
            except Exception as e:
                logger.warning(f"Unable to normalize value '{original_value}': {e}")
