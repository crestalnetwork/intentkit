from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.tools.base import IntentKitTool


class CrwBaseTool(IntentKitTool):
    """Base class for fastCRW tools.

    fastCRW is a Firecrawl-compatible web scraper that ships as a single binary
    and runs self-hosted or on the managed cloud. The REST surface mirrors
    Firecrawl, so these tools mirror the Firecrawl provider with a different
    base URL (CRW_API_URL, default https://fastcrw.com/api) and key (CRW_API_KEY).
    """

    def get_api_key(self):
        # Self-hosted fastCRW may run without auth, so the key is optional there.
        return config.crw_api_key

    def get_api_url(self) -> str:
        base = (config.crw_api_url or "https://fastcrw.com/api").rstrip("/")
        return base

    category: str = "crw"
