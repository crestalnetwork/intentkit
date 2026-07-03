"""Composio REST client (v3.1 API).

Thin async wrapper over the endpoints IntentKit needs for team links:
auth configs, connected-account link flows, and Tool Router sessions
(which expose a hosted MCP endpoint per session).

Uses the raw REST API via httpx instead of the ``composio`` SDK: the SDK is
sync-first and churns quickly, while these few v3.1 endpoints are stable and
easy to call directly. Endpoint paths and payload shapes follow the official
API (https://docs.composio.dev, verified against composio-client 1.41.0).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from intentkit.config.config import config

logger = logging.getLogger(__name__)

_TIMEOUT = 30

# Shared connection pool for all Composio API calls (same pattern as
# clients/moralis.py); auth is per-request, so one pool serves everything.
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=_TIMEOUT)
    return _http_client


# Auth config ids are stable per toolkit within a Composio project; cache them
# for the process lifetime so link attempts skip the lookup. Evicted via
# evict_auth_config when a cached id turns out to be stale (deleted/disabled).
_auth_config_cache: dict[str, str] = {}


def evict_auth_config(toolkit: str) -> None:
    """Drop a cached auth config id so the next lookup resolves it afresh."""
    _ = _auth_config_cache.pop(toolkit, None)


class ComposioError(Exception):
    """A Composio API call failed."""


class ComposioNotConfiguredError(ComposioError):
    """COMPOSIO_API_KEY is not configured."""


class ComposioNoAuthConfigError(ComposioError):
    """The toolkit has no auth config and Composio-managed auth is unavailable.

    Raised for toolkits (e.g. Twitter) that require operator-supplied OAuth
    credentials: the operator must create an auth config for the toolkit in
    the Composio dashboard first.
    """


@dataclass(frozen=True)
class ComposioSession:
    """A Tool Router session bound to one user, exposing a hosted MCP URL."""

    session_id: str
    mcp_url: str


@dataclass(frozen=True)
class ComposioLinkRequest:
    """An initiated connected-account link the user completes via OAuth."""

    connected_account_id: str
    redirect_url: str


class ComposioClient:
    """Async client for the Composio v3.1 REST API."""

    def __init__(self, api_key: str, base_url: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    @property
    def mcp_headers(self) -> dict[str, str]:
        """Headers required to reach a session's hosted MCP endpoint."""
        return {"x-api-key": self._api_key}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}/api/v3.1{path}"
        resp = await _get_http_client().request(
            method,
            url,
            json=json,
            params=params,
            headers={"x-api-key": self._api_key},
        )
        if resp.status_code >= 400:
            # Composio error bodies carry a message; surface it but cap the
            # length so a huge HTML error page can't flood logs or API errors.
            raise ComposioError(
                f"Composio API {method} {path} failed "
                f"({resp.status_code}): {resp.text[:500]}"
            )
        return resp.json()

    async def get_or_create_auth_config(self, toolkit: str) -> str:
        """Return an auth config id for the toolkit (cached per process),
        creating a Composio-managed one if none exists yet.

        Raises ComposioNoAuthConfigError when the toolkit has no auth config
        and managed auth is unavailable (the operator must create one in the
        Composio dashboard, e.g. for Twitter).
        """
        cached = _auth_config_cache.get(toolkit)
        if cached:
            return cached
        data = await self._request(
            "GET", "/auth_configs", params={"toolkit_slug": toolkit}
        )
        for item in data.get("items", []):
            if item.get("status", "ENABLED") == "ENABLED":
                _auth_config_cache[toolkit] = item["id"]
                return item["id"]

        try:
            created = await self._request(
                "POST",
                "/auth_configs",
                json={
                    "toolkit": {"slug": toolkit},
                    "auth_config": {
                        "type": "use_composio_managed_auth",
                        "name": f"intentkit-{toolkit}",
                    },
                },
            )
        except ComposioError as e:
            raise ComposioNoAuthConfigError(
                f"Toolkit '{toolkit}' has no auth config and Composio-managed "
                f"auth could not be created; create an auth config for it in "
                f"the Composio dashboard. ({e})"
            ) from e
        auth_config_id = created["auth_config"]["id"]
        _auth_config_cache[toolkit] = auth_config_id
        return auth_config_id

    async def initiate_link(
        self, user_id: str, auth_config_id: str, callback_url: str
    ) -> ComposioLinkRequest:
        """Create a connected-account link session; the user completes the
        auth flow at the returned redirect URL."""
        data = await self._request(
            "POST",
            "/connected_accounts/link",
            json={
                "user_id": user_id,
                "auth_config_id": auth_config_id,
                "callback_url": callback_url,
            },
        )
        return ComposioLinkRequest(
            connected_account_id=data["connected_account_id"],
            redirect_url=data["redirect_url"],
        )

    async def get_connected_account(self, account_id: str) -> dict[str, Any]:
        """Fetch a connected account (status, toolkit, state, ...)."""
        return await self._request("GET", f"/connected_accounts/{account_id}")

    async def list_connected_accounts(self, user_id: str) -> list[dict[str, Any]]:
        """List connected accounts belonging to a user id (first 100).

        One IntentKit team maps to one Composio user, so a single large page
        covers any realistic number of links.
        """
        data = await self._request(
            "GET", "/connected_accounts", params={"user_ids": user_id, "limit": 100}
        )
        items = data.get("items", [])
        return items if isinstance(items, list) else []

    async def delete_connected_account(self, account_id: str) -> None:
        """Delete a connected account at Composio."""
        await self._request("DELETE", f"/connected_accounts/{account_id}")

    async def create_session(
        self,
        user_id: str,
        toolkits: list[str],
        connected_accounts: dict[str, list[str]] | None = None,
    ) -> ComposioSession:
        """Create a Tool Router session scoped to the given toolkits.

        ``connected_accounts`` pins the exact accounts (per toolkit slug) the
        session may act through, so tools never fall back to accounts linked
        outside IntentKit. Multi-account mode is always on to allow several
        pinned accounts per toolkit. The agent-facing connection manager and
        the code sandbox are disabled: linking happens in the IntentKit UI,
        and the workbench tools are out of scope for team links.
        """
        body: dict[str, Any] = {
            "user_id": user_id,
            "toolkits": {"enable": toolkits},
            "manage_connections": {"enable": False},
            "multi_account": {"enable": True},
            "workbench": {"enable": False},
        }
        if connected_accounts:
            body["connected_accounts"] = connected_accounts
        data = await self._request("POST", "/tool_router/session", json=body)
        return ComposioSession(
            session_id=data["session_id"],
            mcp_url=data["mcp"]["url"],
        )


def composio_configured() -> bool:
    """Whether the Composio integration is configured on this deployment."""
    return bool(config.composio_api_key)


def get_composio_client() -> ComposioClient:
    """Build a client from system config.

    Raises ComposioNotConfiguredError when COMPOSIO_API_KEY is unset.
    """
    if not config.composio_api_key:
        raise ComposioNotConfiguredError("COMPOSIO_API_KEY is not configured")
    return ComposioClient(config.composio_api_key, config.composio_base_url)
