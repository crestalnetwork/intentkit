"""Tests for intentkit.clients.composio (request shapes + response parsing)."""

import json
from unittest.mock import patch

import httpx
import pytest

import intentkit.clients.composio as composio_module
from intentkit.clients.composio import (
    ComposioClient,
    ComposioError,
    ComposioNoAuthConfigError,
    ComposioNotConfiguredError,
    get_composio_client,
)

BASE = "https://backend.composio.dev"


@pytest.fixture(autouse=True)
def clean_module_state(monkeypatch):
    """Isolate the module's shared HTTP client and auth-config cache."""
    monkeypatch.setattr(composio_module, "_http_client", None)
    monkeypatch.setattr(composio_module, "_auth_config_cache", {})


@pytest.fixture
def client_factory(monkeypatch):
    """Build a ComposioClient whose HTTP layer is served by a handler."""

    def factory(handler) -> ComposioClient:
        monkeypatch.setattr(
            composio_module,
            "_http_client",
            httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        return ComposioClient("test-key", BASE)

    return factory


class TestRequestBasics:
    @pytest.mark.asyncio
    async def test_api_key_header_and_path(self, client_factory):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["key"] = request.headers.get("x-api-key")
            return httpx.Response(200, json={"items": []})

        client = client_factory(handler)
        await client.list_connected_accounts("team-t1")

        assert seen["key"] == "test-key"
        assert seen["url"].startswith(f"{BASE}/api/v3.1/connected_accounts")
        assert "user_ids=team-t1" in seen["url"]

    @pytest.mark.asyncio
    async def test_error_status_raises(self, client_factory):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "bad key"})

        client = client_factory(handler)
        with pytest.raises(ComposioError, match="401"):
            await client.list_connected_accounts("u")


class TestAuthConfigs:
    @pytest.mark.asyncio
    async def test_existing_oauth2_config_preferred(self, client_factory):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            assert request.url.params["toolkit_slug"] == "gmail"
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"id": "ac_old", "status": "DISABLED", "auth_scheme": "OAUTH2"},
                        {"id": "ac_key", "status": "ENABLED", "auth_scheme": "API_KEY"},
                        {"id": "ac_good", "status": "ENABLED", "auth_scheme": "OAUTH2"},
                    ]
                },
            )

        client = client_factory(handler)
        # The enabled API_KEY config is skipped: OAuth2-only policy.
        assert await client.get_or_create_auth_config("gmail") == "ac_good"

    @pytest.mark.asyncio
    async def test_creates_managed_oauth2_config_when_missing(self, client_factory):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, request.url.path))
            if request.url.path == "/api/v3.1/auth_configs" and request.method == "GET":
                return httpx.Response(200, json={"items": []})
            if request.url.path == "/api/v3.1/toolkits/notion":
                return httpx.Response(
                    200,
                    json={
                        "slug": "notion",
                        "composio_managed_auth_schemes": ["OAUTH2"],
                    },
                )
            body = json.loads(request.content)
            assert body["toolkit"] == {"slug": "notion"}
            assert body["auth_config"]["type"] == "use_composio_managed_auth"
            return httpx.Response(
                200, json={"auth_config": {"id": "ac_new", "auth_scheme": "OAUTH2"}}
            )

        client = client_factory(handler)
        assert await client.get_or_create_auth_config("notion") == "ac_new"
        assert [m for m, _ in calls] == ["GET", "GET", "POST"]

    @pytest.mark.asyncio
    async def test_id_cached_until_evicted(self, client_factory):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.method)
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"id": "ac_1", "status": "ENABLED", "auth_scheme": "OAUTH2"}
                    ]
                },
            )

        client = client_factory(handler)
        assert await client.get_or_create_auth_config("gmail") == "ac_1"
        assert await client.get_or_create_auth_config("gmail") == "ac_1"
        assert calls == ["GET"]  # second call served from cache

        composio_module.evict_auth_config("gmail")
        assert await client.get_or_create_auth_config("gmail") == "ac_1"
        assert calls == ["GET", "GET"]

    @pytest.mark.asyncio
    async def test_no_managed_oauth2_raises_without_creating(self, client_factory):
        posts = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                posts.append(request.url.path)
            if request.url.path == "/api/v3.1/toolkits/twitter":
                return httpx.Response(
                    200,
                    json={"slug": "twitter", "composio_managed_auth_schemes": []},
                )
            return httpx.Response(200, json={"items": []})

        client = client_factory(handler)
        with pytest.raises(ComposioNoAuthConfigError, match="twitter"):
            await client.get_or_create_auth_config("twitter")
        assert posts == []  # never creates a non-OAuth2 fallback config

    @pytest.mark.asyncio
    async def test_non_oauth2_managed_result_discarded(self, client_factory):
        """If managed creation resolves to a key scheme anyway, the config is
        deleted and the operator is pointed at the dashboard."""
        deletes = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/v3.1/toolkits/supabase":
                return httpx.Response(
                    200,
                    json={
                        "slug": "supabase",
                        "composio_managed_auth_schemes": ["OAUTH2", "API_KEY"],
                    },
                )
            if request.method == "POST":
                return httpx.Response(
                    200,
                    json={"auth_config": {"id": "ac_bad", "auth_scheme": "API_KEY"}},
                )
            if request.method == "DELETE":
                deletes.append(request.url.path)
                return httpx.Response(200, json={})
            return httpx.Response(200, json={"items": []})

        client = client_factory(handler)
        with pytest.raises(ComposioNoAuthConfigError, match="API_KEY"):
            await client.get_or_create_auth_config("supabase")
        assert deletes == ["/api/v3.1/auth_configs/ac_bad"]


class TestLinkFlow:
    @pytest.mark.asyncio
    async def test_initiate_link(self, client_factory):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v3.1/connected_accounts/link"
            body = json.loads(request.content)
            assert body == {
                "user_id": "team-t1",
                "auth_config_id": "ac_1",
                "callback_url": "https://app/oauth/callback",
            }
            return httpx.Response(
                200,
                json={
                    "connected_account_id": "ca_1",
                    "redirect_url": "https://composio/redirect",
                    "link_token": "tok",
                    "expires_at": "2026-07-03T00:00:00Z",
                },
            )

        client = client_factory(handler)
        result = await client.initiate_link(
            "team-t1", "ac_1", "https://app/oauth/callback"
        )
        assert result.connected_account_id == "ca_1"
        assert result.redirect_url == "https://composio/redirect"

    @pytest.mark.asyncio
    async def test_delete_connected_account(self, client_factory):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["path"] = request.url.path
            return httpx.Response(200, json={"success": True})

        client = client_factory(handler)
        await client.delete_connected_account("ca_1")
        assert seen == {
            "method": "DELETE",
            "path": "/api/v3.1/connected_accounts/ca_1",
        }


class TestSessions:
    @pytest.mark.asyncio
    async def test_create_session_body_and_parse(self, client_factory):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v3.1/tool_router/session"
            body = json.loads(request.content)
            assert body["user_id"] == "team-t1"
            assert body["toolkits"] == {"enable": ["gmail", "notion"]}
            assert body["manage_connections"] == {"enable": False}
            assert body["multi_account"] == {"enable": True}
            assert body["workbench"] == {"enable": False}
            assert body["connected_accounts"] == {"gmail": ["ca_1"]}
            return httpx.Response(
                200,
                json={
                    "session_id": "sess_1",
                    "mcp": {"type": "http", "url": "https://mcp.composio.dev/x"},
                    "tool_router_tools": ["COMPOSIO_SEARCH_TOOLS"],
                    "config": {},
                    "config_version": 1,
                },
            )

        client = client_factory(handler)
        session = await client.create_session(
            "team-t1", ["gmail", "notion"], {"gmail": ["ca_1"]}
        )
        assert session.session_id == "sess_1"
        assert session.mcp_url == "https://mcp.composio.dev/x"

    @pytest.mark.asyncio
    async def test_create_session_without_pinning(self, client_factory):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert "connected_accounts" not in body
            return httpx.Response(
                200,
                json={"session_id": "s", "mcp": {"type": "http", "url": "u"}},
            )

        client = client_factory(handler)
        await client.create_session("team-t1", ["gmail"])


class TestFactory:
    def test_unconfigured_raises(self):
        with patch.object(composio_module.config, "composio_api_key", None):
            with pytest.raises(ComposioNotConfiguredError):
                get_composio_client()

    def test_configured_builds_client(self):
        with (
            patch.object(composio_module.config, "composio_api_key", "k"),
            patch.object(
                composio_module.config, "composio_base_url", "https://b.example/"
            ),
        ):
            client = get_composio_client()
        assert client.mcp_headers == {"x-api-key": "k"}
