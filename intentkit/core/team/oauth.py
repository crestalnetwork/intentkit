"""OAuth / install flows for centralized team channels (Slack, Lark).

Each team installs the single official app into its OWN workspace/enterprise.
The provider redirects back to the SPA, which calls the authenticated
``/lead/oauth/complete`` endpoint; completion runs here, gated by the team
admin's session. The signed ``state`` carries everything needed to route and
authorize the completion — ``team_id``, ``channel``, and the initiating
``user_id`` — so a phished install link can't bind a victim's workspace to the
attacker's team (confused-deputy): only the admin who started the install —
proven by the JWT on the complete call matching the state's ``user_id`` — can
finish it.

SECURITY: ``state`` is the CSRF / session-binding guard for the OAuth redirect.
``complete_oauth`` verifies it (signature + freshness + admin match) before
acting on any callback.
"""

import base64
import hashlib
import hmac
import logging
import time
from urllib.parse import urlencode

import httpx

from intentkit.config.config import config
from intentkit.core.team.channel import upsert_channel_config
from intentkit.core.team.membership import check_permission
from intentkit.models.team import TeamRole

logger = logging.getLogger(__name__)

_STATE_MAX_AGE = 600  # seconds


class OAuthStateError(ValueError):
    """The OAuth ``state`` is invalid, expired, or doesn't match the admin."""


class OAuthForbiddenError(PermissionError):
    """The completing user isn't an admin of the team the state was minted for."""


def _state_secret() -> str:
    secret = config.oauth_state_secret
    if not secret:
        raise RuntimeError("OAUTH_STATE_SECRET is not configured")
    return secret


def sign_state(team_id: str, channel_type: str, user_id: str) -> str:
    """HMAC-sign ``team_id:channel:user_id:timestamp`` into an opaque state token.

    The state carries the routing (team + channel) and the session binding
    (user_id), so completion needs nothing from the client but ``code`` + this.
    """
    payload = f"{team_id}:{channel_type}:{user_id}:{int(time.time())}"
    sig = hmac.new(
        _state_secret().encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()


def verify_state(state: str) -> tuple[str, str, str] | None:
    """Return ``(team_id, channel, user_id)`` for a valid, fresh state, else None."""
    try:
        # Restore any base64 padding a proxy / URL parser may have stripped from
        # the redirected ``state`` param (urlsafe_b64decode requires it).
        padded = state + "=" * (-len(state) % 4)
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
        # team_id is leftmost so it tolerates colons; channel/user_id are
        # colon-free (a channel keyword and an opaque user id).
        team_id, channel_type, user_id, ts_str, sig = raw.rsplit(":", 4)
    except Exception:
        return None
    payload = f"{team_id}:{channel_type}:{user_id}:{ts_str}"
    expected = hmac.new(
        _state_secret().encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        if int(time.time()) - int(ts_str) > _STATE_MAX_AGE:
            return None
    except ValueError:
        return None
    return team_id, channel_type, user_id


async def complete_oauth(user_id: str, code: str, state: str) -> tuple[str, str]:
    """Finish an OAuth install for the authenticated admin. Returns
    ``(team_id, channel)``.

    All authorization lives here: the ``state`` must be valid + fresh, its
    ``user_id`` must equal the caller (session-binding), and the caller must be
    an admin of the state's team. Then the per-channel exchange runs. Raises
    OAuthStateError (bad/foreign state) or OAuthForbiddenError (not an admin).
    """
    parsed = verify_state(state)
    if parsed is None:
        raise OAuthStateError("OAuth state is invalid or expired")
    team_id, channel, state_user = parsed
    if state_user != user_id:
        raise OAuthStateError("OAuth state was issued for a different user")
    if not await check_permission(team_id, user_id, TeamRole.ADMIN):
        raise OAuthForbiddenError("Admin or owner role required")

    if channel == "slack":
        await _complete_slack(team_id, user_id, code)
    elif channel == "lark":
        await _complete_lark(team_id, user_id, code)
    else:
        raise OAuthStateError(f"Unknown OAuth channel: {channel}")
    return team_id, channel


# ---------------------------------------------------------------------------
# Slack — distributed OAuth app ("Add to Slack")
# ---------------------------------------------------------------------------

_SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
_SLACK_ACCESS_URL = "https://slack.com/api/oauth.v2.access"


def slack_install_url(team_id: str, user_id: str) -> str:
    """Build the "Add to Slack" URL a team admin follows to install the app.

    ``redirect_uri`` points at the SPA's OAuth landing page, which relays the
    code + state to ``complete_oauth`` with the admin's session.
    """
    if not config.slack_client_id:
        raise RuntimeError("Slack OAuth is not configured")
    params = {
        "client_id": config.slack_client_id,
        "scope": config.slack_oauth_scopes,
        "redirect_uri": config.oauth_redirect_uri,
        "state": sign_state(team_id, "slack", user_id),
    }
    return f"{_SLACK_AUTHORIZE_URL}?{urlencode(params)}"


async def _complete_slack(team_id: str, user_id: str, code: str) -> None:
    """Exchange a Slack OAuth code and store the workspace install on its team.

    The caller (``complete_oauth``) has already verified the admin + state.
    Raises RuntimeError on a missing config or an exchange failure.
    """
    if not (config.slack_client_id and config.slack_client_secret):
        raise RuntimeError("Slack OAuth is not configured")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            _SLACK_ACCESS_URL,
            data={
                "client_id": config.slack_client_id,
                "client_secret": config.slack_client_secret,
                "code": code,
                "redirect_uri": config.oauth_redirect_uri,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack OAuth error: {data.get('error')}")

    team = data.get("team") or {}
    # Guard against an ok-but-empty response so we never store (and enable) a
    # half-install whose workspace_id/bot_token is null (it would never route).
    if not team.get("id") or not data.get("access_token"):
        raise RuntimeError("Slack OAuth response missing workspace id or bot token")

    await upsert_channel_config(
        team_id,
        "slack",
        {
            "workspace_id": team.get("id"),
            "workspace_name": team.get("name"),
            "bot_token": data.get("access_token"),
            "bot_user_id": data.get("bot_user_id"),
        },
        created_by=user_id,
    )
    logger.info("Slack workspace %s installed for team %s", team.get("id"), team_id)


# ---------------------------------------------------------------------------
# Lark / Feishu — ISV (store) app authorization
# ---------------------------------------------------------------------------

_LARK_AUTH_HOSTS = {
    "feishu": "https://open.feishu.cn",
    "lark": "https://open.larksuite.com",
}


def lark_install_url(team_id: str, user_id: str) -> str:
    """Build the Lark authorization URL a team admin follows to authorize the
    ISV app for their enterprise.

    ``redirect_uri`` points at the SPA's OAuth landing page; the code->tenant_key
    exchange runs in the Go webhook service (it owns the token chain), reached via
    ``_complete_lark``.
    """
    if not config.lark_app_id:
        raise RuntimeError("Lark OAuth is not configured")
    host = _LARK_AUTH_HOSTS.get(config.lark_domain, _LARK_AUTH_HOSTS["feishu"])
    params = {
        "app_id": config.lark_app_id,
        "redirect_uri": config.oauth_redirect_uri,
        "state": sign_state(team_id, "lark", user_id),
    }
    return f"{host}/open-apis/authen/v1/authorize?{urlencode(params)}"


async def _complete_lark(team_id: str, user_id: str, code: str) -> None:
    """Run the ISV code->tenant_key exchange in the Go Lark service (which
    persists the install on the team's channel row).

    The caller (``complete_oauth``) has already verified the admin + state.
    ``user_id`` is forwarded so the stored install is attributed to the
    installing admin (matching the Slack path), not the team.

    Raises RuntimeError if the Lark service is unconfigured or the exchange fails.
    """
    if not config.lark_service_url or not config.lark_internal_secret:
        raise RuntimeError("Lark service (LARK_SERVICE_URL/SECRET) is not configured")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{config.lark_service_url.rstrip('/')}/lark/exchange",
            json={"code": code, "team_id": team_id, "created_by": user_id},
            headers={"X-Internal-Secret": config.lark_internal_secret},
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Lark exchange failed: status {resp.status_code}")
    logger.info("Lark enterprise authorized for team %s", team_id)
