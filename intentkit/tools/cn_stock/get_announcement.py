"""Listed-company announcements (公告) via akshare."""

from typing import Any

import akshare as ak
from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.tools.cn_stock.base import CNStockBaseTool, today_cn


class GetAnnouncementInput(BaseModel):
    on_date: str | None = Field(
        default=None,
        description="Date in YYYYMMDD; defaults to today. Announcements are released after market close.",
    )
    limit: int = Field(
        default=20,
        description="Maximum number of items to return (1-100).",
        ge=1,
        le=100,
    )


class GetAnnouncement(CNStockBaseTool):
    name: str = "cn_stock_get_announcement"
    title: str = "Get Announcement"
    description: str = (
        "Get the day's listed-company announcements (财报、重大事项、增持减持、停复牌等). "
        "Use to surface material disclosures that may move stock prices."
    )
    args_schema: ArgsSchema | None = GetAnnouncementInput

    async def _arun(
        self,
        on_date: str | None = None,
        limit: int = 20,
        **_: Any,
    ) -> list[dict[str, Any]]:
        d = on_date or today_cn().strftime("%Y%m%d")
        rows: list[dict[str, Any]] = await self.run_blocking(
            f"announce:{d}",
            900,
            ak.stock_notice_report,
            symbol="全部",
            date=d,
        )
        return rows[:limit] if rows else []
