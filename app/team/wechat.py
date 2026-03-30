"""Team API WeChat QR code login flow endpoints."""

import logging

from fastapi import APIRouter, Body, Depends, Query

from intentkit.core.team.channel import set_team_channel
from intentkit.models.team_channel import TeamChannel

from app.common.wechat import (
    WechatConnectRequest,
    WechatQrCodeResponse,
    WechatQrStatusResponse,
    fetch_wechat_qrcode,
    poll_wechat_qrcode,
)
from app.team.auth import verify_team_admin

logger = logging.getLogger(__name__)

team_wechat_router = APIRouter(tags=["Team WeChat"])


@team_wechat_router.get(
    "/teams/{team_id}/wechat/qrcode",
    response_model=WechatQrCodeResponse,
    operation_id="team_get_wechat_qrcode",
    summary="Get WeChat login QR code (Team)",
    tags=["Team WeChat"],
)
async def get_wechat_qrcode(
    auth: tuple[str, str] = Depends(verify_team_admin),
):
    """Call iLink API to generate a QR code for WeChat bot login."""
    return await fetch_wechat_qrcode()


@team_wechat_router.get(
    "/teams/{team_id}/wechat/qrcode/status",
    response_model=WechatQrStatusResponse,
    operation_id="team_poll_wechat_qrcode_status",
    summary="Poll WeChat QR code scan status (Team)",
    tags=["Team WeChat"],
)
async def poll_wechat_qrcode_status(
    qrcode: str = Query(..., description="QR code UUID from get_wechat_qrcode"),
    auth: tuple[str, str] = Depends(verify_team_admin),
):
    """Poll iLink API for QR code scan confirmation status."""
    return await poll_wechat_qrcode(qrcode)


@team_wechat_router.post(
    "/teams/{team_id}/wechat/connect",
    response_model=TeamChannel,
    operation_id="team_connect_wechat_channel",
    summary="Save WeChat credentials after QR scan (Team)",
    tags=["Team WeChat"],
)
async def connect_wechat_channel(
    request: WechatConnectRequest = Body(...),
    auth: tuple[str, str] = Depends(verify_team_admin),
):
    """Save WeChat bot credentials to team_channels after successful QR scan."""
    user_id, team_id = auth
    config: dict[str, object] = {
        "bot_token": request.bot_token,
        "baseurl": request.baseurl,
        "ilink_bot_id": request.ilink_bot_id,
        "user_id": request.user_id,
    }
    return await set_team_channel(team_id, "wechat", config, created_by=user_id)
