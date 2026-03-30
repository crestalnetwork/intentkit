"""Shared WeChat types and helpers for local and team API routers."""

import httpx
from pydantic import BaseModel

from intentkit.utils.error import IntentKitAPIError

ILINK_BASE_URL = "https://ilinkai.weixin.qq.com"

ilink_http_client = httpx.AsyncClient(timeout=30)


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


async def fetch_wechat_qrcode() -> WechatQrCodeResponse:
    """Call iLink API to generate a QR code for WeChat bot login."""
    resp = await ilink_http_client.get(
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


async def poll_wechat_qrcode(qrcode: str) -> WechatQrStatusResponse:
    """Poll iLink API for QR code scan confirmation status."""
    try:
        resp = await ilink_http_client.get(
            f"{ILINK_BASE_URL}/ilink/bot/get_qrcode_status",
            params={"qrcode": qrcode},
        )
    except httpx.ReadTimeout:
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
