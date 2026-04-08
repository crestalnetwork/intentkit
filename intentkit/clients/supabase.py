"""Supabase Admin API client for identity management."""

import logging
from typing import Any

import httpx

from intentkit.config.config import config

logger = logging.getLogger(__name__)

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=10)
    return _http_client


def _get_headers() -> dict[str, str]:
    """Build auth headers for Supabase Admin API."""
    key = config.supabase_service_role_key or ""
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }


async def get_user_identities(user_id: str) -> list[dict[str, Any]]:
    """Fetch user identities from Supabase Admin API.

    Args:
        user_id: The Supabase user UUID.

    Returns:
        List of identity dicts, or empty list on error.
    """
    supabase_url = config.supabase_url
    service_role_key = config.supabase_service_role_key
    if not supabase_url or not service_role_key:
        logger.warning("Supabase not configured, cannot fetch identities")
        return []

    url = f"{supabase_url}/auth/v1/admin/users/{user_id}"
    try:
        client = _get_http_client()
        resp = await client.get(url, headers=_get_headers())
        resp.raise_for_status()
        data = resp.json()
        return data.get("identities") or []
    except Exception as e:
        logger.error("Failed to fetch identities for user %s: %s", user_id, e)
        return []


async def unlink_identity(user_id: str, identity_id: str) -> bool:
    """Unlink an identity from a Supabase user.

    Args:
        user_id: The Supabase user UUID.
        identity_id: The identity UUID to unlink.

    Returns:
        True on success, False on failure.
    """
    supabase_url = config.supabase_url
    service_role_key = config.supabase_service_role_key
    if not supabase_url or not service_role_key:
        logger.warning("Supabase not configured, cannot unlink identity")
        return False

    url = f"{supabase_url}/auth/v1/admin/users/{user_id}/identities/{identity_id}"
    try:
        client = _get_http_client()
        resp = await client.delete(url, headers=_get_headers())
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(
            "Failed to unlink identity %s for user %s: %s",
            identity_id,
            user_id,
            e,
        )
        return False


def parse_linked_providers(
    identities: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Extract linked providers from Supabase identity list.

    Args:
        identities: Raw identity list from Supabase Admin API.

    Returns:
        Dict with provider keys: {"google": {...}, "evm": {...}}.
        Each value contains relevant fields and identity_id for unlinking.
    """
    result: dict[str, dict[str, Any]] = {}
    for identity in identities:
        provider = identity.get("provider")
        identity_data = identity.get("identity_data") or {}

        if provider == "google":
            result["google"] = {
                "email": identity_data.get("email"),
                "identity_id": identity.get("id"),
                "linked": True,
            }
        elif provider == "web3":
            chain = identity_data.get("chain")
            address = identity_data.get("address")
            if address and (chain == "ethereum" or chain is None):
                result["evm"] = {
                    "address": address,
                    "identity_id": identity.get("id"),
                    "linked": True,
                }
    return result
