"""User profile endpoints (not team-scoped)."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Body, Depends, File, Response, UploadFile
from pydantic import BaseModel, Field, TypeAdapter
from sqlalchemy import update

from intentkit.clients.supabase import (
    get_user_identities,
    parse_linked_providers,
    unlink_identity,
)
from intentkit.config.config import config
from intentkit.config.db import get_session
from intentkit.config.redis import get_redis
from intentkit.core.team.membership import check_permission
from intentkit.models.team import Team, TeamPlan, TeamRole, TeamTable
from intentkit.models.user import User, UserUpdate
from intentkit.utils.error import IntentKitAPIError
from intentkit.utils.upload import validate_and_store_image

from app.team.auth import get_current_user

_team_list_adapter = TypeAdapter(list[Team])

team_user_router = APIRouter()

logger = logging.getLogger(__name__)

USER_CACHE_PREFIX = "intentkit:user:"
USER_CACHE_TTL = 3600  # 1 hour

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=10)
    return _http_client


async def invalidate_user_cache(user_id: str) -> None:
    """Delete user cache entry from Redis."""
    try:
        redis = get_redis()
        await redis.delete(f"{USER_CACHE_PREFIX}{user_id}")
    except Exception as e:
        logger.warning("Failed to invalidate user cache for %s: %s", user_id, e)


async def _sync_supabase_user(user_id: str) -> User:
    """Fetch user details from Supabase Admin API and upsert locally."""
    supabase_url = config.supabase_url
    service_role_key = config.supabase_service_role_key
    if not supabase_url or not service_role_key:
        logger.warning("Supabase URL or service role key not configured, skip sync")
        existing = await User.get(user_id)
        if existing:
            return existing
        return await UserUpdate.model_validate({}).patch(user_id)

    url = f"{supabase_url}/auth/v1/admin/users/{user_id}"
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
    }

    try:
        client = _get_http_client()
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error("Failed to fetch user %s from Supabase: %s", user_id, e)
        existing = await User.get(user_id)
        if existing:
            return existing
        return await UserUpdate.model_validate({}).patch(user_id)

    # Load existing user to check current state
    existing_user = await User.get(user_id)

    update_fields: dict[str, Any] = {}
    if data.get("email"):
        update_fields["email"] = data["email"]

    user_metadata = data.get("user_metadata") or {}
    if user_metadata.get("full_name"):
        update_fields.setdefault("extra", {})
        update_fields["extra"]["full_name"] = user_metadata["full_name"]
    if user_metadata.get("avatar_url"):
        update_fields.setdefault("extra", {})
        update_fields["extra"]["avatar_url"] = user_metadata["avatar_url"]

    # Extract wallet addresses and linked accounts from identities
    linked_accounts: dict[str, Any] = {}
    has_google = False
    evm_address: str | None = None
    for identity in data.get("identities") or []:
        provider = identity.get("provider")
        identity_data = identity.get("identity_data") or {}

        if provider == "google":
            has_google = True
            linked_accounts["google"] = {
                "email": identity_data.get("email"),
                "identity_id": identity.get("id"),
            }
        elif provider == "web3":
            address = identity_data.get("address")
            chain = identity_data.get("chain")
            if address and chain == "ethereum":
                evm_address = address
                update_fields["evm_wallet_address"] = address
                linked_accounts["evm"] = {
                    "address": address,
                    "identity_id": identity.get("id"),
                }
            elif address and chain == "solana":
                update_fields["solana_wallet_address"] = address

    update_fields["linked_accounts"] = linked_accounts

    # Sync name: only set if user has no name yet (don't overwrite user-edited name)
    if not (existing_user and existing_user.name):
        if has_google and user_metadata.get("full_name"):
            update_fields["name"] = user_metadata["full_name"]
        elif evm_address:
            update_fields["name"] = f"{evm_address[:6]}...{evm_address[-4:]}"

    # Sync avatar: from Google avatar_url if user has no avatar yet
    google_avatar = user_metadata.get("avatar_url")
    if google_avatar and has_google:
        if not (existing_user and existing_user.avatar):
            update_fields["avatar"] = google_avatar

    update_fields["synced_at"] = datetime.now(UTC)

    return await UserUpdate.model_validate(update_fields).patch(user_id)


async def _get_user_with_cache(user_id: str) -> tuple[str, bool]:
    """Get user JSON with Redis caching. Returns (json_str, from_cache)."""
    redis = get_redis()
    cache_key = f"{USER_CACHE_PREFIX}{user_id}"

    try:
        cached = await redis.get(cache_key)
        if cached:
            return (cached, True)
    except Exception as e:
        logger.warning("Redis cache read failed for user %s: %s", user_id, e)

    user = await _sync_supabase_user(user_id)
    json_str = user.model_dump_json()

    try:
        await redis.set(cache_key, json_str, ex=USER_CACHE_TTL)
    except Exception as e:
        logger.warning("Redis cache write failed for user %s: %s", user_id, e)

    return (json_str, False)


def _linked_accounts_response(providers: dict[str, dict[str, Any]]) -> Response:
    """Build a JSON response with linked account info."""
    result = {
        "google": providers.get("google"),
        "evm": providers.get("evm"),
    }
    return Response(content=json.dumps(result), media_type="application/json")


class SwitchTeamRequest(BaseModel):
    team_id: str


@team_user_router.get("/user")
async def get_user(
    user_id: str = Depends(get_current_user),
) -> Response:
    """Get the current user's profile. Syncs from Supabase on cache miss."""
    json_str, _ = await _get_user_with_cache(user_id)
    return Response(content=json_str, media_type="application/json")


@team_user_router.get("/user/teams")
async def list_user_teams(
    user_id: str = Depends(get_current_user),
) -> Response:
    """List all teams the current user belongs to (for team switcher)."""
    teams = await Team.get_by_user(user_id)
    return Response(
        content=_team_list_adapter.dump_json(teams),
        media_type="application/json",
    )


@team_user_router.post("/user/switch-team")
async def switch_team(
    body: SwitchTeamRequest = Body(...),
    user_id: str = Depends(get_current_user),
) -> Response:
    """Switch the user's active team."""
    is_member = await check_permission(body.team_id, user_id, TeamRole.MEMBER)
    if not is_member:
        raise IntentKitAPIError(
            status_code=403,
            key="NotTeamMember",
            message="Not a member of this team",
        )

    user = await UserUpdate.model_validate({"current_team_id": body.team_id}).patch(
        user_id
    )
    await invalidate_user_cache(user_id)

    return Response(content=user.model_dump_json(), media_type="application/json")


@team_user_router.get("/user/linked-accounts")
async def get_linked_accounts(
    user_id: str = Depends(get_current_user),
) -> Response:
    """Get the user's linked identity providers from Supabase."""
    identities = await get_user_identities(user_id)
    providers = parse_linked_providers(identities)
    return _linked_accounts_response(providers)


class UnlinkAccountRequest(BaseModel):
    provider: str


@team_user_router.post("/user/unlink-account")
async def unlink_account(
    body: UnlinkAccountRequest = Body(...),
    user_id: str = Depends(get_current_user),
) -> Response:
    """Unlink an identity provider from the user's account.

    Only EVM wallet can be unlinked, and only if Google is already linked.
    """
    if body.provider != "evm":
        raise IntentKitAPIError(
            status_code=400,
            key="CannotUnlink",
            message="Only EVM wallet can be unlinked",
        )

    identities = await get_user_identities(user_id)
    providers = parse_linked_providers(identities)

    if "google" not in providers:
        raise IntentKitAPIError(
            status_code=400,
            key="GoogleRequired",
            message="Must have Google linked before unlinking EVM wallet",
        )

    evm_info = providers.get("evm")
    if not evm_info:
        raise IntentKitAPIError(
            status_code=400,
            key="NotLinked",
            message="EVM wallet is not linked",
        )

    identity_id = evm_info.get("identity_id")
    if not identity_id:
        raise IntentKitAPIError(
            status_code=400,
            key="MissingIdentityId",
            message="Cannot determine EVM identity to unlink",
        )

    success = await unlink_identity(user_id, identity_id)
    if not success:
        raise IntentKitAPIError(
            status_code=500,
            key="UnlinkFailed",
            message="Failed to unlink EVM wallet from Supabase",
        )

    # Clear wallet address on user record
    await UserUpdate.model_validate({"evm_wallet_address": None}).patch(user_id)
    await invalidate_user_cache(user_id)

    # Return updated state: EVM removed, Google remains
    providers.pop("evm", None)
    return _linked_accounts_response(providers)


class UpdateProfileRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    avatar: str | None = None


@team_user_router.patch("/user/profile")
async def update_profile(
    body: UpdateProfileRequest = Body(...),
    user_id: str = Depends(get_current_user),
) -> Response:
    """Update the current user's profile (name and/or avatar)."""
    update_data: dict[str, Any] = {}
    if body.name is not None:
        update_data["name"] = body.name
    if body.avatar is not None:
        # Empty string clears the avatar
        update_data["avatar"] = body.avatar or None

    if not update_data:
        raise IntentKitAPIError(
            status_code=400,
            key="NoFieldsToUpdate",
            message="No fields to update",
        )

    user = await UserUpdate.model_validate(update_data).patch(user_id)
    await invalidate_user_cache(user_id)
    return Response(content=user.model_dump_json(), media_type="application/json")


@team_user_router.post("/user/upload-avatar")
async def upload_user_avatar(
    file: UploadFile = File(..., description="Image file to upload as user avatar"),
    user_id: str = Depends(get_current_user),
) -> dict[str, str]:
    """Upload an image to S3 for use as user avatar.

    Accepts image files (JPEG, PNG, GIF, WebP). Max size 5MB.
    """
    path = await validate_and_store_image(file, "avatars/user/")
    return {"path": path}


@team_user_router.post("/user/post-link-sync")
async def post_link_sync(
    user_id: str = Depends(get_current_user),
) -> Response:
    """Called after linking a new identity. Re-syncs and checks for plan upgrades.

    If Google is now linked and user's first owned team has plan=NONE,
    upgrade it to FREE.
    """
    # Invalidate cache and re-sync from Supabase
    await invalidate_user_cache(user_id)
    user = await _sync_supabase_user(user_id)

    # Use linked_accounts from the just-synced user to check for plan upgrade
    linked = user.linked_accounts or {}
    if "google" in linked:
        await _maybe_upgrade_first_team(user_id)

    # Re-cache the user
    json_str = user.model_dump_json()
    try:
        redis = get_redis()
        await redis.set(f"{USER_CACHE_PREFIX}{user_id}", json_str, ex=USER_CACHE_TTL)
    except Exception as e:
        logger.warning("Redis cache write failed for user %s: %s", user_id, e)

    return Response(content=json_str, media_type="application/json")


async def _maybe_upgrade_first_team(user_id: str) -> None:
    """If user's first owned team has NONE plan, upgrade to FREE."""
    first_team_id = await User.get_first_owned_team_id(user_id)
    if not first_team_id:
        return

    team = await Team.get(first_team_id)
    if not team or team.plan != TeamPlan.NONE:
        return

    async with get_session() as db:
        await db.execute(
            update(TeamTable)
            .where(TeamTable.id == first_team_id)
            .values(plan=TeamPlan.FREE.value)
        )
        await db.commit()
    logger.info(
        "Upgraded team %s to FREE plan after Google link for user %s",
        first_team_id,
        user_id,
    )
