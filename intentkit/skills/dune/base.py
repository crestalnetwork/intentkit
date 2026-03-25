"""Base module for Dune skills.

Provides shared functionality for interacting with the Dune API.
"""

import asyncio
import logging
import time
from typing import Any

import httpx
from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill

logger = logging.getLogger(__name__)

BASE_URL = "https://api.dune.com/api/v1"


class DuneBaseTool(IntentKitSkill):
    """Base class for Dune skills.

    Provides shared HTTP, polling, and result formatting helpers.
    """

    category: str = "dune"

    def get_api_key(self) -> str:
        if not config.dune_api_key:
            raise ToolException("Dune API key is not configured")
        return config.dune_api_key

    async def _dune_request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated request to the Dune API.

        Args:
            method: HTTP method (GET, POST).
            path: API path (appended to BASE_URL).
            json_body: Optional JSON body for POST requests.
            params: Optional query parameters.

        Returns:
            Parsed JSON response.
        """
        api_key = self.get_api_key()
        url = f"{BASE_URL}{path}"
        headers = {"x-dune-api-key": api_key}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    json=json_body,
                    params=params,
                )
                if response.status_code != 200:
                    raise ToolException(
                        f"Dune API error: {response.status_code} - {response.text}"
                    )
                return response.json()
        except ToolException:
            raise
        except Exception as e:
            logger.error("Dune API request failed: %s", e, exc_info=True)
            raise ToolException(f"Dune API request failed: {e}")

    async def _poll_execution(
        self, execution_id: str, max_wait: int = 120
    ) -> dict[str, Any]:
        """Poll a Dune execution until completion.

        Uses linear backoff: 2s, 4s, 6s, ... capped at 10s.

        Args:
            execution_id: The execution ID to poll.
            max_wait: Maximum seconds to wait before timing out.

        Returns:
            The final status response with state QUERY_STATE_COMPLETED.
        """
        deadline = time.monotonic() + max_wait
        interval = 2

        while time.monotonic() < deadline:
            status = await self._dune_request(
                "GET", f"/execution/{execution_id}/status"
            )
            state = status.get("state")

            if state == "QUERY_STATE_COMPLETED":
                return status
            if state in (
                "QUERY_STATE_FAILED",
                "QUERY_STATE_CANCELLED",
                "QUERY_STATE_EXPIRED",
            ):
                raise ToolException(f"Dune query {state}: {status}")

            await asyncio.sleep(interval)
            interval = min(interval + 2, 10)

        raise ToolException(
            f"Dune query timed out after {max_wait}s (execution: {execution_id})"
        )

    async def _get_results(self, execution_id: str, limit: int) -> dict[str, Any]:
        """Fetch results for a completed execution."""
        return await self._dune_request(
            "GET",
            f"/execution/{execution_id}/results",
            params={"limit": limit},
        )

    def format_results(self, result_json: dict[str, Any], query_id: int | str) -> str:
        """Format Dune query results as readable text.

        Args:
            result_json: Raw JSON response from the results endpoint.
            query_id: The query ID for the header.

        Returns:
            Formatted string with header, column names, and pipe-separated rows.
        """
        result = result_json.get("result", {})
        metadata = result.get("metadata", {})
        rows = result.get("rows", [])
        columns = metadata.get("column_names", [])
        executed_at = metadata.get("executed_at", "N/A")
        row_count = metadata.get("total_row_count", len(rows))

        header = (
            f"Query {query_id} results ({row_count} rows, executed at {executed_at})"
        )

        if not rows:
            return f"{header}\n\nNo rows returned."

        if not columns:
            columns = list(rows[0].keys()) if rows else []

        col_header = " | ".join(columns)
        lines = [header, "", col_header, "-" * min(len(col_header), 80)]

        char_count = sum(len(line) for line in lines)
        max_chars = 4000

        for row in rows:
            row_str = " | ".join(str(row.get(col, "")) for col in columns)
            char_count += len(row_str) + 1
            if char_count > max_chars:
                lines.append(f"... truncated ({row_count} total rows)")
                break
            lines.append(row_str)

        return "\n".join(lines)
