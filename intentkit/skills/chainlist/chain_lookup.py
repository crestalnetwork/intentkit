import logging
from typing import Any, Dict, List, Optional, Type

import httpx
from pydantic import BaseModel, Field

from intentkit.skills.chainlist.base import ChainlistBaseTool

logger = logging.getLogger(__name__)


class ChainLookupInput(BaseModel):
    """Input for ChainLookup tool."""

    search_term: Optional[str] = Field(
        description="Term to search for (chain name, symbol, or chain ID)",
        default=None,
    )
    chain_id: Optional[int] = Field(
        description="Specific chain ID to look up",
        default=None,
    )
    no_tracking: Optional[bool] = Field(
        description="Whether to return only RPC endpoints with no tracking",
        default=False,
    )
    limit: Optional[int] = Field(
        description="Limit the number of results returned",
        default=5,
    )


class ChainLookup(ChainlistBaseTool):
    """Tool for looking up blockchain RPC endpoints from Chainlist."""

    name: str = "chain_lookup"
    description: str = (
        "Look up blockchain RPC endpoints and details by chain name, symbol, or chain ID.\n"
        "Returns information about blockchains including RPC endpoints, native currency, and explorers."
    )
    args_schema: Type[BaseModel] = ChainLookupInput

    def _normalize_text(self, text: str) -> str:
        """Normalize text for searching (lowercase, remove spaces)."""
        if not text:
            return ""
        return text.lower().strip()

    async def _fetch_chains_data(self) -> List[Dict[str, Any]]:
        """Fetch chains data from Chainlist API."""
        chainlist_api_url = "https://chainlist.org/rpcs.json"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(chainlist_api_url)
            response.raise_for_status()
            return response.json()

    def _filter_chains(
        self,
        chains: List[Dict[str, Any]],
        search_term: Optional[str] = None,
        chain_id: Optional[int] = None,
        no_tracking: bool = False,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Filter chains based on search criteria."""
        filtered_chains = chains

        # Filter by chain_id if provided
        if chain_id is not None:
            filtered_chains = [
                chain for chain in filtered_chains if chain.get("chainId") == chain_id
            ]

        # Filter by search term if provided
        if search_term and chain_id is None:
            normalized_term = self._normalize_text(search_term)
            result = []

            for chain in filtered_chains:
                name = self._normalize_text(chain.get("name", ""))
                symbol = self._normalize_text(chain.get("chain", ""))
                short_name = self._normalize_text(chain.get("shortName", ""))

                if (
                    normalized_term in name
                    or normalized_term in symbol
                    or normalized_term in short_name
                ):
                    result.append(chain)

            filtered_chains = result

        # Filter RPC endpoints for each chain if no_tracking is True
        if no_tracking:
            filtered_result = []
            for chain in filtered_chains:
                if "rpc" not in chain:
                    continue

                chain_copy = dict(chain)
                chain_copy["rpc"] = [
                    rpc
                    for rpc in chain["rpc"]
                    if isinstance(rpc, dict) and rpc.get("tracking") == "none"
                ]

                if chain_copy[
                    "rpc"
                ]:  # Only include if it has RPC endpoints after filtering
                    filtered_result.append(chain_copy)

            filtered_chains = filtered_result

        # Apply limit
        if limit > 0:
            filtered_chains = filtered_chains[:limit]

        return filtered_chains

    def _format_chain(self, chain: Dict[str, Any]) -> Dict[str, Any]:
        """Format a chain entry for response."""
        # Format RPC endpoints
        formatted_rpcs = []
        if "rpc" in chain:
            for rpc in chain["rpc"]:
                if isinstance(rpc, dict):
                    url = rpc.get("url")
                    tracking = rpc.get("tracking", "unspecified")
                    formatted_rpcs.append({"url": url, "tracking": tracking})
                elif isinstance(rpc, str):
                    formatted_rpcs.append({"url": rpc, "tracking": "unspecified"})

        # Format chain data
        formatted_chain = {
            "name": chain.get("name"),
            "chain": chain.get("chain"),
            "chainId": chain.get("chainId"),
            "networkId": chain.get("networkId"),
            "shortName": chain.get("shortName"),
            "infoURL": chain.get("infoURL", ""),
            "nativeCurrency": chain.get("nativeCurrency", {}),
            "rpc": formatted_rpcs[:3],  # Limit to 3 RPC endpoints per chain
            "total_rpc_count": len(chain.get("rpc", [])),
        }

        # Add explorers if available
        if "explorers" in chain and chain["explorers"]:
            formatted_chain["explorers"] = [
                {"name": explorer.get("name", ""), "url": explorer.get("url", "")}
                for explorer in chain["explorers"][:2]  # Limit to 2 explorers
            ]

        return formatted_chain

    async def _arun(
        self,
        search_term: Optional[str] = None,
        chain_id: Optional[int] = None,
        no_tracking: Optional[bool] = False,
        limit: Optional[int] = 5,
        config: Optional[Any] = None,
        **kwargs,
    ) -> Dict:
        """Lookup blockchain RPC endpoints from Chainlist."""
        if not search_term and not chain_id:
            return {
                "error": "Please provide either a search term or a chain ID to lookup."
            }

        try:
            # Fetch data
            chains_data = await self._fetch_chains_data()

            # Filter chains based on criteria
            filtered_chains = self._filter_chains(
                chains_data,
                search_term=search_term,
                chain_id=chain_id,
                no_tracking=no_tracking,
                limit=limit,
            )

            # Handle no results
            if not filtered_chains:
                return {
                    "found": False,
                    "message": "No chains found matching the search criteria.",
                }

            # Format results
            formatted_chains = [self._format_chain(chain) for chain in filtered_chains]

            return {
                "found": True,
                "count": len(formatted_chains),
                "chains": formatted_chains,
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching chain data: {e}")
            return {
                "error": f"Error fetching chain data: HTTP status code {e.response.status_code}"
            }
        except Exception as e:
            logger.error(f"Error fetching chain data: {str(e)}")
            return {"error": f"An error occurred while fetching chain data: {str(e)}"}
