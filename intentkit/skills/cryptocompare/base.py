"""Base class for all CryptoCompare tools."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Type

import httpx
from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill
from intentkit.utils.error import RateLimitExceeded

CRYPTO_COMPARE_BASE_URL = "https://min-api.cryptocompare.com"

logger = logging.getLogger(__name__)


class CryptoCompareBaseTool(IntentKitSkill):
    """Base class for CryptoCompare tools.

    This class provides common functionality for all CryptoCompare API tools:
    - Rate limiting
    - API client handling
    - State management through skill_store
    """

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )

    @property
    def category(self) -> str:
        return "cryptocompare"

    async def check_rate_limit(
        self, agent_id: str, max_requests: int = 1, interval: int = 15
    ) -> None:
        """Check if the rate limit has been exceeded.

        Args:
            agent_id: The ID of the agent.
            max_requests: Maximum number of requests allowed within the rate limit window.
            interval: Time interval in minutes for the rate limit window.

        Raises:
            RateLimitExceeded: If the rate limit has been exceeded.
        """
        rate_limit = await self.skill_store.get_agent_skill_data(
            agent_id, self.name, "rate_limit"
        )

        current_time = datetime.now(tz=timezone.utc)

        if (
            rate_limit
            and rate_limit.get("reset_time")
            and rate_limit["count"] is not None
            and datetime.fromisoformat(rate_limit["reset_time"]) > current_time
        ):
            if rate_limit["count"] >= max_requests:
                raise RateLimitExceeded("Rate limit exceeded")

            rate_limit["count"] += 1
            await self.skill_store.save_agent_skill_data(
                agent_id, self.name, "rate_limit", rate_limit
            )

            return

        # If no rate limit exists or it has expired, create a new one
        new_rate_limit = {
            "count": 1,
            "reset_time": (current_time + timedelta(minutes=interval)).isoformat(),
        }
        await self.skill_store.save_agent_skill_data(
            agent_id, self.name, "rate_limit", new_rate_limit
        )
        return

    async def fetch_price(
        self, api_key: str, from_symbol: str, to_symbols: List[str]
    ) -> dict:
        """Fetch current price for a cryptocurrency in multiple currencies.

        Args:
            api_key: The CryptoCompare API key
            from_symbol: Base cryptocurrency symbol to get prices for (e.g., 'BTC', 'ETH')
            to_symbols: List of target currencies (fiat or crypto) (e.g., ['USD', 'EUR', 'JPY'])

        Returns:
            Dict containing the price data
        """
        url = f"{CRYPTO_COMPARE_BASE_URL}/data/price"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}

        # Ensure from_symbol is a string, not a list
        if isinstance(from_symbol, list):
            from_symbol = from_symbol[0] if from_symbol else ""

        # Ensure to_symbols is a list
        if not isinstance(to_symbols, list):
            to_symbols = [to_symbols] if to_symbols else ["USD"]

        params = {
            "fsym": from_symbol.upper(),
            "tsyms": ",".join([s.upper() for s in to_symbols]),
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers)
        if response.status_code != 200:
            logger.error(f"API returned status code {response.status_code}")
            return {"error": f"API returned status code {response.status_code}"}
        return response.json()

    async def fetch_trading_signals(self, api_key: str, from_symbol: str) -> dict:
        """Fetch the latest trading signals.

        Args:
            api_key: The CryptoCompare API key
            from_symbol: Cryptocurrency symbol to fetch trading signals for (e.g., 'BTC')

        Returns:
            Dict containing the trading signals data
        """
        url = f"{CRYPTO_COMPARE_BASE_URL}/data/tradingsignals/intotheblock/latest"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}

        # Ensure from_symbol is a string, not a list
        if isinstance(from_symbol, list):
            from_symbol = from_symbol[0] if from_symbol else ""

        params = {"fsym": from_symbol.upper()}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers)
        if response.status_code != 200:
            logger.error(f"API returned status code {response.status_code}")
            return {"error": f"API returned status code {response.status_code}"}
        return response.json()

    async def fetch_top_market_cap(
        self, api_key: str, limit: int, to_symbol: str = "USD"
    ) -> dict:
        """Fetch top cryptocurrencies by market cap.

        Args:
            api_key: The CryptoCompare API key
            limit: Number of cryptocurrencies to fetch
            to_symbol: Quote currency for market cap calculation (e.g., 'USD', 'EUR')

        Returns:
            Dict containing the top market cap data
        """
        url = f"{CRYPTO_COMPARE_BASE_URL}/data/top/mktcapfull"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}

        # Ensure to_symbol is a string, not a list
        if isinstance(to_symbol, list):
            to_symbol = to_symbol[0] if to_symbol else "USD"

        params = {"limit": limit, "tsym": to_symbol.upper()}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers)
        if response.status_code != 200:
            logger.error(f"API returned status code {response.status_code}")
            return {"error": f"API returned status code {response.status_code}"}
        return response.json()

    async def fetch_top_exchanges(
        self, api_key: str, from_symbol: str, to_symbol: str = "USD"
    ) -> dict:
        """Fetch top exchanges for a cryptocurrency pair.

        Args:
            api_key: The CryptoCompare API key
            from_symbol: Base cryptocurrency symbol for the trading pair (e.g., 'BTC')
            to_symbol: Quote currency symbol for the trading pair. Defaults to 'USD'

        Returns:
            Dict containing the top exchanges data
        """
        url = f"{CRYPTO_COMPARE_BASE_URL}/data/top/exchanges"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}

        # Ensure from_symbol and to_symbol are strings, not lists
        if isinstance(from_symbol, list):
            from_symbol = from_symbol[0] if from_symbol else ""
        if isinstance(to_symbol, list):
            to_symbol = to_symbol[0] if to_symbol else "USD"

        params = {"fsym": from_symbol.upper(), "tsym": to_symbol.upper()}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers)
        if response.status_code != 200:
            logger.error(f"API returned status code {response.status_code}")
            return {"error": f"API returned status code {response.status_code}"}
        return response.json()

    async def fetch_top_volume(
        self, api_key: str, limit: int, to_symbol: str = "USD"
    ) -> dict:
        """Fetch top cryptocurrencies by total volume.

        Args:
            api_key: The CryptoCompare API key
            limit: Number of cryptocurrencies to fetch
            to_symbol: Quote currency for volume calculation. Defaults to 'USD'

        Returns:
            Dict containing the top volume data
        """
        url = f"{CRYPTO_COMPARE_BASE_URL}/data/top/totalvolfull"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}

        # Ensure to_symbol is a string, not a list
        if isinstance(to_symbol, list):
            to_symbol = to_symbol[0] if to_symbol else "USD"

        params = {"limit": limit, "tsym": to_symbol.upper()}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers)
        if response.status_code != 200:
            logger.error(f"API returned status code {response.status_code}")
            return {"error": f"API returned status code {response.status_code}"}
        return response.json()

    async def fetch_news(self, api_key: str, token: str, timestamp: int = None) -> dict:
        """Fetch news for a specific token and timestamp.

        Args:
            api_key: The CryptoCompare API key
            token: Token symbol to fetch news for (e.g., BTC, ETH, SOL)
            timestamp: Optional timestamp for fetching news

        Returns:
            Dict containing the news data
        """
        url = f"{CRYPTO_COMPARE_BASE_URL}/data/v2/news/"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}

        # Ensure token is a string, not a list
        if isinstance(token, list):
            token = token[0] if token else ""

        params = {"categories": token.upper()}
        if timestamp:
            params["lTs"] = timestamp

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers)
        if response.status_code != 200:
            logger.error(f"API returned status code {response.status_code}")
            return {"error": f"API returned status code {response.status_code}"}
        return response.json()


# Response Models
class CryptoPrice(BaseModel):
    """Model representing a cryptocurrency price."""

    from_symbol: str
    to_symbol: str
    price: float


class CryptoNews(BaseModel):
    """Model representing a cryptocurrency news article."""

    id: str
    published_on: int
    title: str
    url: str
    body: str
    tags: str
    categories: str
    source: str
    source_info: Dict[str, Any] = Field(default_factory=dict)


class CryptoExchange(BaseModel):
    """Model representing a cryptocurrency exchange."""

    exchange: str
    from_symbol: str
    to_symbol: str
    volume24h: float
    volume24h_to: float


class CryptoCurrency(BaseModel):
    """Model representing a cryptocurrency."""

    id: str
    name: str
    symbol: str
    full_name: str
    market_cap: float = 0
    volume24h: float = 0
    price: float = 0
    change24h: float = 0
