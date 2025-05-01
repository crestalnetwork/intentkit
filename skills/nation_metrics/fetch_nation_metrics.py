"""Skill to fetch Crestal Nation metrics from Dune Analytics API.

Retrieves data for specified metrics (e.g., total users, unique_ai_citizens) or all metrics.
"""

import difflib
import re
from typing import Any, Dict, Type

import httpx
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from abstracts.skill import SkillStoreABC
from skills.nation_metrics.base import NationBaseTool

SUPPORTED_METRICS = {
    "total_users": 4858003,
    "weekly_active_users": 4867200,
    "unique_ai_citizens": 4857629,
    "unique_creators": 4844506,
    "ai_citizens_over_time": 4857629,
    "chat_messages_over_time": 4857870,
    "onchain_transactions": 4859895,
    "total_chat_messages": 4857870,
    "daily_skill_executions": 4861785,
    "goods_services": 4859895,
    "agent_tvl": 4859887,
    "citizen_market_cap": 4859887,
}
METRIC_ALIASES = {
    "agents": "unique_ai_citizens",
    "citizens": "unique_ai_citizens",
    "market_cap": "citizen_market_cap",
    "nation_market_cap": "citizen_market_cap",
    "number_of_agents": "unique_ai_citizens",
    "number_of_citizens": "unique_ai_citizens",
    "ai_citizens": "unique_ai_citizens",
    "users": "total_users",
    "active_users": "weekly_active_users",
    "creators": "unique_creators",
    "transactions": "onchain_transactions",
    "messages": "total_chat_messages",
    "skill_executions": "daily_skill_executions",
    "tvl": "agent_tvl",
}
BASE_URL = "https://api.dune.com/api/v1/query"


class NationMetricsInput(BaseModel):
    """Input schema for fetching Crestal Nation metrics."""

    metric: str = Field(
        default="",
        description="Metric to fetch (e.g., total_users, agents, market_cap). Empty for all metrics.",
    )


class MetricData(BaseModel):
    """Data model for a single Crestal Nation metric's data."""

    metric: str = Field(description="Metric name")
    data: Dict[str, Any] = Field(description="Metric data from Dune API")
    error: str = Field(default="", description="Error message if fetch failed")


class NationMetricsOutput(BaseModel):
    """Output schema for Crestal Nation metrics."""

    metrics: Dict[str, MetricData] = Field(
        description="Dictionary of metric names to their data"
    )
    summary: str = Field(description="Summary of fetched metrics")


class FetchNationMetrics(NationBaseTool):
    """Skill to fetch Crestal Nation metrics from Dune Analytics API."""

    name: str = "fetch_nation_metrics"
    description: str = (
        "Fetches Crestal Nation metrics (e.g., total users, agents/citizens, market cap) from Dune Analytics API. "
        "Supports specific metrics or all metrics if none specified. Handles rate limits with retries."
    )
    args_schema: Type[BaseModel] = NationMetricsInput
    skill_store: SkillStoreABC = Field(description="Skill store for data persistence")

    def normalize_metric(self, metric: str) -> str:
        """Normalize a metric string for matching.

        Args:
            metric: Raw metric string from input.

        Returns:
            Normalized metric string (lowercase, underscores, no punctuation).
        """
        if not metric:
            return ""
        # Convert to lowercase, replace spaces/punctuation with underscores, remove extra underscores
        metric = re.sub(r"[^\w\s]", "", metric.lower()).replace(" ", "_")
        metric = re.sub(r"_+", "_", metric).strip("_")
        return metric

    def find_closest_metrics(self, metric: str, max_suggestions: int = 3) -> list[str]:
        """Find the closest matching metrics using fuzzy matching.

        Args:
            metric: Input metric to match against.
            max_suggestions: Maximum number of suggestions to return.

        Returns:
            List of closest metric names.
        """
        all_metrics = list(SUPPORTED_METRICS.keys()) + list(METRIC_ALIASES.keys())
        if not metric or not all_metrics:
            return []
        # Use difflib to find closest matches
        matches = difflib.get_close_matches(
            metric, all_metrics, n=max_suggestions, cutoff=0.6
        )
        return matches

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=5, min=5, max=60)
    )
    async def fetch_data(
        self, query_id: int, api_key: str, limit: int = 1000
    ) -> Dict[str, Any]:
        """Fetch data for a specific Crestal Nation query from Dune Analytics API.

        Args:
            query_id: Dune query ID.
            api_key: Dune API key.
            limit: Maximum number of results (default 1000).

        Returns:
            Dictionary of query results.

        Raises:
            ToolException: If the API request fails.
        """
        from langchain.tools.base import ToolException

        url = f"{BASE_URL}/{query_id}/results?limit={limit}"
        headers = {"X-Dune-API-Key": api_key}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                return response.json().get("result", {})
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                raise ToolException(f"Error fetching data from Dune API: {e}")

    async def _arun(
        self,
        metric: str = "",
        config: RunnableConfig = None,
        **kwargs,
    ) -> NationMetricsOutput:
        """Fetch Crestal Nation metrics asynchronously.

        Args:
            metric: Metric to fetch (e.g., total_users, agents). Empty for all metrics.
            config: Runnable configuration.
            **kwargs: Additional keyword arguments.

        Returns:
            NationMetricsOutput with metric data and summary.
        """
        import logging

        logger = logging.getLogger(__name__)
        context = self.context_from_config(config)
        api_key = self.get_api_key(context)

        # Normalize metric
        metric = self.normalize_metric(metric)

        # Handle aliases
        metric = METRIC_ALIASES.get(metric, metric)

        results = {}
        metrics_to_fetch = (
            SUPPORTED_METRICS
            if not metric
            else (
                {metric: SUPPORTED_METRICS[metric]}
                if metric in SUPPORTED_METRICS
                else {}
            )
        )

        if not metrics_to_fetch:
            closest_metrics = self.find_closest_metrics(metric)
            supported = ", ".join(SUPPORTED_METRICS.keys())
            suggestions = (
                f" Did you mean: {', '.join(closest_metrics)}?"
                if closest_metrics
                else ""
            )
            logger.warning(
                "Unrecognized metric: %s. Suggested: %s", metric, closest_metrics
            )
            return NationMetricsOutput(
                metrics={},
                summary=(
                    f"Invalid metric: {metric}. Supported metrics include: {supported}.{suggestions} "
                    "Try 'fetch crestal nation metrics total_users' or submit a feature request at "
                    "https://github.com/crestalnetwork/intentkit."
                ),
            )

        for metric_name, query_id in metrics_to_fetch.items():
            try:
                data = await self.fetch_data(query_id, api_key)
                results[metric_name] = MetricData(metric=metric_name, data=data)
            except Exception as e:
                results[metric_name] = MetricData(
                    metric=metric_name, data={}, error=str(e)
                )

        summary = f"Fetched data for {len([m for m in results.values() if not m.error])}/{len(metrics_to_fetch)} metrics."
        if any(m.error for m in results.values()):
            summary += f" Errors occurred for: {', '.join(m.metric for m in results.values() if m.error)}."

        return NationMetricsOutput(metrics=results, summary=summary)

    def _run(self, question: str):
        raise NotImplementedError("Use _arun for async execution")
