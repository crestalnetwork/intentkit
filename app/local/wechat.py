"""IntentKit Local WeChat API Router.

Provides endpoints for WeChat QR code login flow and channel connection.
The frontend calls these endpoints to initiate WeChat bot login via iLink API.
"""

import logging

import httpx
from fastapi import APIRouter, Body, Query
from pydantic import BaseModel

from intentkit.core.team.channel import set_team_channel
from intentkit.models.team_channel import TeamChannel
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)

wechat_router = APIRouter(tags=["WeChat"])

ILINK_BASE_URL = "https://ilinkai.weixin.qq.com"

# Reusable HTTP client for iLink API calls
_ilink_http_client = httpx.AsyncClient(timeout=30)

# Hardcoded IDs for local single-user development (same as lead.py)
LEAD_TEAM_ID = "system"
LEAD_USER_ID = "system"


class WechatQrCodeResponse(BaseModel):
    """Response from QR code generation."""

    qrcode: str
    qrcode_img_content: str


class WechatQrStatusResponse(BaseModel):
    """Response from QR code status polling."""

    status: str
    bot_token: str | None = None
    baseurl: str | None = None
    ilink_bot_id: str | None = None
    user_id: str | None = None


class WechatConnectRequest(BaseModel):
    """Request body for connecting WeChat channel."""

    bot_token: str
    baseurl: str
    ilink_bot_id: str
    user_id: str


@wechat_router.get(
    "/wechat/qrcode",
    response_model=WechatQrCodeResponse,
    operation_id="get_wechat_qrcode",
    summary="Get WeChat login QR code",
)
async def get_wechat_qrcode():
    """Call iLink API to generate a QR code for WeChat bot login."""
    resp = await _ilink_http_client.get(
        f"{ILINK_BASE_URL}/ilink/bot/get_bot_qrcode",
        params={"bot_type": "3"},
    )
    if resp.status_code != 200:
        raise IntentKitAPIError(
            502, "WechatApiError", f"iLink API returned {resp.status_code}"
        )
    data = resp.json()
    if "qrcode" not in data:
        raise IntentKitAPIError(
            502, "WechatApiError", "iLink API did not return qrcode"
        )
    return WechatQrCodeResponse(
        qrcode=data["qrcode"],
        qrcode_img_content=data.get("qrcode_img_content", ""),
    )


@wechat_router.get(
    "/wechat/qrcode/status",
    response_model=WechatQrStatusResponse,
    operation_id="poll_wechat_qrcode_status",
    summary="Poll WeChat QR code scan status",
)
async def poll_wechat_qrcode_status(
    qrcode: str = Query(..., description="QR code UUID from get_wechat_qrcode"),
):
    """Poll iLink API for QR code scan confirmation status."""
    try:
        resp = await _ilink_http_client.get(
            f"{ILINK_BASE_URL}/ilink/bot/get_qrcode_status",
            params={"qrcode": qrcode},
        )
    except httpx.ReadTimeout:
        # iLink holds the connection for long-polling; return pending on timeout
        return WechatQrStatusResponse(status="pending")
    if resp.status_code != 200:
        raise IntentKitAPIError(
            502, "WechatApiError", f"iLink API returned {resp.status_code}"
        )
    data = resp.json()
    return WechatQrStatusResponse(
        status=data.get("status", "pending"),
        bot_token=data.get("bot_token"),
        baseurl=data.get("baseurl"),
        ilink_bot_id=data.get("ilink_bot_id"),
        user_id=data.get("user_id"),
    )


@wechat_router.post(
    "/wechat/connect",
    response_model=TeamChannel,
    operation_id="connect_wechat_channel",
    summary="Save WeChat credentials after QR scan",
)
async def connect_wechat_channel(
    request: WechatConnectRequest = Body(...),
):
    """Save WeChat bot credentials to team_channels after successful QR scan."""
    config: dict[str, object] = {
        "bot_token": request.bot_token,
        "baseurl": request.baseurl,
        "ilink_bot_id": request.ilink_bot_id,
        "user_id": request.user_id,
    }
    return await set_team_channel(
        LEAD_TEAM_ID, "wechat", config, created_by=LEAD_USER_ID
    )
