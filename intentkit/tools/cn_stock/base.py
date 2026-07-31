"""Base class for cn_stock (Chinese A-share) tools backed by akshare."""

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

import pytz
from langchain_core.tools.base import ToolException

from intentkit.config.redis import get_redis
from intentkit.tools.base import IntentKitTool

logger = logging.getLogger(__name__)

# A-share exchanges all run on Asia/Shanghai. Defaults must follow that wall clock,
# regardless of the server's local timezone (typically UTC in production).
_CN_TZ = pytz.timezone("Asia/Shanghai")


def today_cn() -> date:
    """Return today's date in the Asia/Shanghai timezone."""
    return datetime.now(_CN_TZ).date()


def normalize_a_share_symbol(symbol: str) -> str:
    """Strip exchange prefix/suffix and return a bare 6-digit A-share code.

    Accepts formats like "600519", "sh600519", "SH600519", "600519.SH", "600519.sh".
    """
    s = symbol.strip().upper()
    for prefix in ("SH", "SZ", "BJ"):
        if s.startswith(prefix):
            s = s[len(prefix) :]
            break
    if "." in s:
        s = s.split(".", 1)[0]
    if len(s) != 6 or not s.isdigit():
        raise ToolException(f"Invalid A-share code: {symbol!r} (expect 6 digits)")
    return s


def market_of(symbol: str) -> str:
    """Return the exchange code ("sh"/"sz"/"bj") for a normalized 6-digit code."""
    code = normalize_a_share_symbol(symbol)
    # 920xxx is the BSE prefix introduced in 2025 for new listings; treat it as bj
    # rather than letting all 9xxxxx through (900xxx are SSE B-shares, not A-shares).
    if code.startswith("92"):
        return "bj"
    head = code[0]
    if head == "6":
        return "sh"
    if head in ("0", "3"):
        return "sz"
    if head in ("4", "8"):
        return "bj"
    raise ToolException(f"Cannot infer market for code {code}")


class CNStockBaseTool(IntentKitTool):
    category: str = "cn_stock"

    async def run_blocking(
        self,
        cache_key: str | None,
        cache_ttl: int,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute a blocking akshare call off the event loop with optional caching.

        Pass cache_key=None to skip the cache for live data that must never be stale.
        """
        redis = get_redis() if cache_key is not None else None
        if redis is not None:
            cached = await redis.get(f"cn_stock:{cache_key}")
            if cached:
                try:
                    return json.loads(cached)
                except (TypeError, ValueError):
                    logger.warning("Bad cache payload for %s, refetching", cache_key)

        # akshare scrapes free public endpoints which rate-limit by IP; cap shared use.
        await self.global_rate_limit_by_category(limit=60, seconds=60)

        try:
            result = await asyncio.to_thread(func, *args, **kwargs)
        except Exception as e:
            raise ToolException(f"akshare call failed: {e}") from e

        if hasattr(result, "to_json"):
            payload_str = result.to_json(
                orient="records", date_format="iso", force_ascii=False
            )
            payload: Any = json.loads(payload_str)
        elif isinstance(result, (str, int, float, bool, list, dict)) or result is None:
            payload = result
            payload_str = json.dumps(payload, ensure_ascii=False, default=str)
        else:
            payload = str(result)
            payload_str = json.dumps(payload, ensure_ascii=False)

        if redis is not None:
            await redis.set(f"cn_stock:{cache_key}", payload_str, ex=cache_ttl)
        return payload
