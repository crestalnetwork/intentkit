"""Team links: link external app accounts (Composio) and expose their tools.

Flow, mirroring the channel OAuth installs in ``core/team/oauth.py``:

1. A member picks a whitelisted app on the Links page; ``initiate_team_link``
   asks Composio for a hosted auth link and records a *pending* link row keyed
   by the Composio connected-account id.
2. The browser follows the redirect URL; Composio runs the provider OAuth and
   sends the browser back to the SPA's ``/oauth/callback`` page with
   ``connected_account_id`` (+ ``status``) query params.
3. The SPA relays the id to the authenticated complete endpoint;
   ``complete_team_link`` authorizes the caller, verifies the account is
   ACTIVE **at Composio** (query params are never trusted), and activates the
   row.

Levels: team-level apps are linked/unlinked by team admins and shared with
every member; user-level apps are linked by each member for themselves, and
only the owning user (or an admin) may unlink them. Either way, all accounts
live under the team's single Composio user (``team-{team_id}``) — the level
is an IntentKit concept, enforced here and by session pinning.

SECURITY: the pending row is the CSRF / session-binding guard — the
connected-account id routes the callback to its team, and completion requires
the caller to be the user who initiated the link (like the signed ``state``
in the channel OAuth flow), holding the role its level demands.

Active links are exposed to the team's lead agent as MCP tools: a fresh
Composio Tool Router session is created per executor build (executors are
cached ~1h per team+user and invalidated on link changes), pinned to exactly
the team-level accounts plus the current user's own user-level accounts, and
its hosted MCP endpoint provides the ``COMPOSIO_*`` tools.
"""

from __future__ import annotations

import logging

from langchain_core.tools import BaseTool
from pydantic import BaseModel

from intentkit.clients.composio import (
    ComposioError,
    composio_configured,
    evict_auth_config,
    get_composio_client,
)
from intentkit.config.config import config
from intentkit.core.team.membership import check_permission
from intentkit.models.team import TeamRole
from intentkit.models.team_link import (
    LINK_APPS,
    LINK_CATEGORIES,
    LINK_LEVEL_TEAM,
    LINK_LEVEL_USER,
    LINK_STATUS_ACTIVE,
    LINK_STATUS_PENDING,
    TeamLink,
)

logger = logging.getLogger(__name__)


def _invalidate_lead_cache(team_id: str, user_id: str | None = None) -> None:
    """Invalidate cached lead executors so toolsets and prompts pick up the
    link change — just one user's executor when a user-level link changed
    (``user_id``), the whole team's otherwise.

    Imported lazily: ``intentkit.core.lead`` imports this module (the lead
    engine builds the Links prompt section and tools), so a top-level import
    would be circular.
    """
    from intentkit.core.lead.cache import invalidate_lead_cache

    invalidate_lead_cache(team_id, user_id)


def _invalidate_for_link(link: TeamLink) -> None:
    """Invalidate the executors a specific link change can affect."""
    _invalidate_lead_cache(
        link.team_id, link.user_id if link.level == LINK_LEVEL_USER else None
    )


class LinkStateError(ValueError):
    """The link attempt is invalid, expired, or references an unknown app."""


class LinkForbiddenError(PermissionError):
    """The caller isn't allowed to manage this team's links."""


async def _check_link_role(team_id: str, user_id: str, level: str) -> None:
    """Raise LinkForbiddenError unless the caller holds the role a link
    level demands: admin for team-level apps, plain membership for
    user-level apps (each member manages their own accounts)."""
    required = TeamRole.ADMIN if level == LINK_LEVEL_TEAM else TeamRole.MEMBER
    if not await check_permission(team_id, user_id, required):
        raise LinkForbiddenError(
            "Admin or owner role required"
            if required == TeamRole.ADMIN
            else "Team membership required"
        )


class LinkAppInfo(BaseModel):
    """One whitelisted app with the links visible to the requesting user."""

    app: str
    name: str
    description: str
    level: str
    categories: list[str]
    links: list[TeamLink]


class TeamLinksResponse(BaseModel):
    """The Links page payload: feature availability + per-app link lists.

    ``categories`` is the ordered union of the whitelist's category tags, for
    the UI's filter row.
    """

    enabled: bool
    categories: list[str]
    apps: list[LinkAppInfo]


def composio_user_id(team_id: str) -> str:
    """The Composio user id everything of this team is linked under.

    Matches the lead agent id convention (``team-{team_id}``) — links belong
    to the team, not to individual members.
    """
    return f"team-{team_id}"


def links_page_url(team_id: str) -> str:
    """The SPA URL of the team's Links page (shown to users in the prompt).

    The local single-user deployment uses the synthetic ``system`` team and an
    un-prefixed frontend route.
    """
    base = config.app_base_url.rstrip("/")
    if team_id == "system":
        return f"{base}/links"
    return f"{base}/t/{team_id}/links"


async def initiate_team_link(
    team_id: str, app: str, user_id: str, verify_roles: bool = True
) -> str:
    """Start linking an account of a whitelisted app; returns the URL the
    caller's browser must visit to run the provider auth flow.

    Team-level apps require an admin (when ``verify_roles``); user-level apps
    may be linked by any member, and the new link belongs to that user.

    Raises LinkStateError for non-whitelisted apps, LinkForbiddenError for
    insufficient roles, and propagates ComposioNotConfiguredError /
    ComposioError from the Composio calls.
    """
    app_def = LINK_APPS.get(app)
    if not app_def:
        raise LinkStateError(f"App '{app}' is not in the linkable whitelist")
    if verify_roles:
        await _check_link_role(team_id, user_id, app_def.level)
    owner_user_id = user_id if app_def.level == LINK_LEVEL_USER else None

    client = get_composio_client()
    auth_config_id = await client.get_or_create_auth_config(app_def.toolkit)
    try:
        request = await client.initiate_link(
            composio_user_id(team_id), auth_config_id, config.oauth_redirect_uri
        )
    except ComposioError:
        # The cached auth config id may have gone stale (deleted/disabled at
        # Composio); evict it so the next attempt re-resolves.
        evict_auth_config(app_def.toolkit)
        raise

    # A new attempt supersedes any earlier one that never completed; also
    # drop the superseded half-open accounts at Composio so they don't
    # accumulate under the team's Composio user. User-level attempts only
    # supersede the same user's — never another member's in-flight link.
    for account_id in await TeamLink.delete_pending_for_app(
        team_id, app, user_id=owner_user_id
    ):
        await _delete_composio_account_quiet(account_id)
    await TeamLink.create(
        team_id,
        app,
        request.connected_account_id,
        user_id,
        level=app_def.level,
        user_id=owner_user_id,
    )
    return request.redirect_url


async def _delete_composio_account_quiet(account_id: str) -> None:
    """Best-effort delete of a connected account at Composio.

    The local row is authoritative; a failed remote delete only leaves
    clutter at Composio (session pinning never exposes unlisted accounts).
    """
    try:
        await get_composio_client().delete_connected_account(account_id)
    except ComposioError as e:
        logger.warning("Failed to delete Composio account %s: %s", account_id, e)


async def complete_team_link(
    user_id: str, connected_account_id: str, verify_roles: bool = True
) -> TeamLink:
    """Finish a link attempt after the OAuth callback. Returns the link.

    Authorization: the caller must be the user who initiated the attempt and
    (when ``verify_roles``, i.e. the team deployment) hold the role the app's
    level demands — admin for team-level, membership for user-level. The
    account status is verified against Composio directly — the redirect's
    query params are never trusted. Idempotent for already-active links, so a
    reloaded callback page doesn't error.
    """
    link = await TeamLink.get_by_connected_account(connected_account_id)
    if not link:
        raise LinkStateError("Unknown or superseded link attempt")
    # Identity first, then the idempotent short-circuit: a reloaded callback
    # page (same user) succeeds again, but other users can't probe a
    # connected account id for its team/app.
    if link.created_by != user_id:
        raise LinkStateError("This link attempt was initiated by a different user")
    if link.status == LINK_STATUS_ACTIVE:
        return link
    if verify_roles:
        await _check_link_role(link.team_id, user_id, link.level)

    account = await get_composio_client().get_connected_account(connected_account_id)
    status = str(account.get("status", "")).upper()
    if status != "ACTIVE":
        if status in ("FAILED", "EXPIRED", "REVOKED"):
            # Terminal failure: drop the attempt locally and at Composio.
            await TeamLink.delete(link.id)
            await _delete_composio_account_quiet(connected_account_id)
        raise LinkStateError(f"Account link did not complete (status: {status})")

    updated = await TeamLink.set_status(
        link.id, LINK_STATUS_ACTIVE, account_label=_extract_label(account)
    )
    _invalidate_for_link(link)
    logger.info(
        "Linked %s account %s for team %s",
        link.app,
        connected_account_id,
        link.team_id,
    )
    return updated or link


async def delete_team_link(
    team_id: str, link_id: str, user_id: str, verify_roles: bool = True
) -> None:
    """Unlink an account: delete it at Composio (best-effort) and locally.

    Authorization (when ``verify_roles``): team-level links require an admin;
    user-level links may be removed by their owning user or an admin.
    """
    link = await TeamLink.get(link_id)
    if not link or link.team_id != team_id:
        raise LinkStateError("Link not found")
    if verify_roles and not (
        (link.level == LINK_LEVEL_USER and link.user_id == user_id)
        or await check_permission(team_id, user_id, TeamRole.ADMIN)
    ):
        raise LinkForbiddenError("Only the link's owner or a team admin can unlink")
    if composio_configured():
        await _delete_composio_account_quiet(link.connected_account_id)
    await TeamLink.delete(link_id)
    _invalidate_for_link(link)


async def list_team_links(team_id: str, user_id: str) -> TeamLinksResponse:
    """The Links page payload: every whitelisted app with the links visible
    to the requesting user (team-level links plus their own user-level ones —
    other members' personal accounts are never exposed).

    Non-pending link statuses are refreshed from Composio best-effort, so an
    account revoked or expired on the provider side shows up here (and stops
    being pinned into lead sessions) without a webhook. The sync covers ALL
    of the team's links, not just the visible ones — one member's page view
    heals everyone's stale statuses from the single Composio response — while
    the response filters down to what the viewer may see.
    """
    links = await TeamLink.list_for_team(team_id)
    if links and composio_configured():
        links = await _sync_link_statuses(team_id, links)
    # Attempts still pending after the sync are in-flight (or abandoned and
    # awaiting cleanup) — not something to show as a linked account. Other
    # members' user-level links stay hidden from this viewer.
    links = [
        link
        for link in links
        if link.status != LINK_STATUS_PENDING
        and (link.level == LINK_LEVEL_TEAM or link.user_id == user_id)
    ]

    apps = [
        LinkAppInfo(
            app=app_def.app,
            name=app_def.name,
            description=app_def.description,
            level=app_def.level,
            categories=list(app_def.categories),
            links=[link for link in links if link.app == app_def.app],
        )
        for app_def in LINK_APPS.values()
    ]
    return TeamLinksResponse(
        enabled=composio_configured(),
        categories=list(LINK_CATEGORIES),
        apps=apps,
    )


async def _sync_link_statuses(team_id: str, links: list[TeamLink]) -> list[TeamLink]:
    """Refresh link statuses from Composio; tolerate any API failure.

    Only accounts present in the response are updated: an absent account may
    just be on a later page, so absence is never treated as revocation.

    Pending rows self-heal here: if the provider OAuth finished but the
    browser never delivered the callback, the account is ACTIVE at Composio
    while the row is stuck pending — activate it (safe: the attempt was
    initiated by a team admin and the status comes from a server-to-server
    call, not from anything a caller controls). Terminally failed pending
    attempts are dropped.
    """
    try:
        accounts = await get_composio_client().list_connected_accounts(
            composio_user_id(team_id)
        )
    except ComposioError as e:
        logger.warning("Composio status sync failed for team %s: %s", team_id, e)
        return links
    account_by_id = {a["id"]: a for a in accounts if a.get("id")}
    updates: dict[str, str] = {}
    toolset_changed = False
    synced: list[TeamLink] = []
    for link in links:
        account = account_by_id.get(link.connected_account_id)
        if account is None:
            synced.append(link)
            continue
        new_status = str(account.get("status", "")).lower()

        if link.status == LINK_STATUS_PENDING:
            if new_status == LINK_STATUS_ACTIVE:
                updated = await TeamLink.set_status(
                    link.id, LINK_STATUS_ACTIVE, account_label=_extract_label(account)
                )
                toolset_changed = True
                synced.append(
                    updated or link.model_copy(update={"status": LINK_STATUS_ACTIVE})
                )
            elif new_status in ("failed", "expired", "revoked"):
                await TeamLink.delete(link.id)
            else:
                synced.append(link)  # OAuth still in flight
            continue

        if new_status and new_status != link.status:
            updates[link.id] = new_status
            # A link entering or leaving "active" changes the lead's toolset.
            if LINK_STATUS_ACTIVE in (link.status, new_status):
                toolset_changed = True
            link = link.model_copy(update={"status": new_status})
        synced.append(link)
    if updates:
        await TeamLink.set_statuses(updates)
    if toolset_changed:
        _invalidate_lead_cache(team_id)
    return synced


async def get_active_links(team_id: str, user_id: str | None) -> list[TeamLink]:
    """The active links usable in one user's conversations: the team-level
    ones plus that user's own user-level ones. ``user_id=None`` returns
    team-level links only (user-agnostic contexts).

    Short-circuits without a query when Composio is unconfigured — links are
    dormant then, and this runs on every cold lead-executor build.
    """
    if not composio_configured():
        return []
    return await TeamLink.list_visible(team_id, user_id, status=LINK_STATUS_ACTIVE)


async def build_lead_link_tools(team_id: str, user_id: str | None) -> list[BaseTool]:
    """Build the lead agent's Composio MCP tools for one user's conversations
    from the team-level links plus the user's own user-level links.

    One Tool Router session is created per cached executor — i.e. per
    (team, user) per cache lifetime, not per team. Sessions are ephemeral on
    Composio's side, but this is the multiplier to look at first if session
    creation ever gets rate-limited.

    Returns [] when the feature is unconfigured, there are no usable active
    links, or Composio is unreachable — link problems must never break the
    lead agent itself.
    """
    links = await get_active_links(team_id, user_id)
    if not links:
        return []

    connected_accounts: dict[str, list[str]] = {}
    for link in links:
        app_def = LINK_APPS.get(link.app)
        if not app_def:
            continue  # app removed from the whitelist; its links go dormant
        connected_accounts.setdefault(app_def.toolkit, []).append(
            link.connected_account_id
        )
    if not connected_accounts:
        return []
    toolkits = list(connected_accounts)

    try:
        # tools.mcp imports the whole tools registry; keep it lazy so plain
        # link CRUD (and its tests) don't pay for it.
        from intentkit.tools.mcp.composio import build_composio_mcp_tools

        session = await get_composio_client().create_session(
            composio_user_id(team_id), toolkits, connected_accounts
        )
        tools: list[BaseTool] = list(await build_composio_mcp_tools(session.mcp_url))
        logger.info(
            "Loaded %d Composio MCP tools for team %s user %s (session %s, toolkits: %s)",
            len(tools),
            team_id,
            user_id,
            session.session_id,
            ", ".join(toolkits),
        )
        return tools
    except Exception:
        logger.exception("Failed to load Composio MCP tools for team %s", team_id)
        return []


def build_links_section(team_id: str, links: list[TeamLink]) -> str:
    """The "Links" system prompt section for the team's lead agent.

    Always present when the feature is configured — the agent must know how
    to guide users to link apps even when nothing is linked yet. ``links``
    must already be the set visible in the current conversation (team-level
    plus the current user's own). Ends with the list of currently linked
    accounts, as consumers rely on.
    """
    if not composio_configured():
        return ""

    team_apps = ", ".join(
        a.name for a in LINK_APPS.values() if a.level == LINK_LEVEL_TEAM
    )
    user_apps = ", ".join(
        a.name for a in LINK_APPS.values() if a.level == LINK_LEVEL_USER
    )
    url = links_page_url(team_id)
    lines = [
        "### Links\n\n",
        "External app accounts can be linked for you to act through, at two levels:\n",
        f"- Team-level apps (linked by a team admin, shared by every member): "
        f"{team_apps}.\n",
        f"- User-level apps (each user links their own account; you act on "
        f"the current user's own account): {user_apps}.\n\n",
        "- When at least one account is linked, you have tools prefixed with "
        "`COMPOSIO_` to search for and execute actions on the linked apps; "
        "prefer them whenever a request involves one of these apps.\n",
        "- If the user asks about one of these apps but no usable account is "
        "linked in this conversation (not linked, or expired/revoked), do not "
        "improvise or claim access. Instead, share this URL and explain who "
        "can link it there — a team admin for team-level apps, the user "
        f"themselves for user-level apps: {url}\n\n",
        "Accounts linked in this conversation:\n",
    ]
    active = [link for link in links if link.status == LINK_STATUS_ACTIVE]
    if active:
        for link in active:
            app_def = LINK_APPS.get(link.app)
            app_name = app_def.name if app_def else link.app
            label = link.account_label or link.connected_account_id
            scope = (
                "current user's account"
                if link.level == LINK_LEVEL_USER
                else "team account"
            )
            lines.append(f"- {app_name} ({scope}): {label}\n")
    else:
        lines.append("- (none yet)\n")
    return "".join(lines)


# Keys probed (in order) in a connected account's ``state.val`` for a
# human-readable identity; tokens and secrets in there are never read.
_LABEL_KEYS = (
    "email",
    "screen_name",
    "username",
    "user_name",
    "login",
    "workspace_name",
    "team_name",
    "account_id",
)


def _extract_label(account: dict[str, object]) -> str | None:
    """Best-effort display label (email/handle/workspace) for an account."""
    state = account.get("state")
    val = state.get("val") if isinstance(state, dict) else None
    if isinstance(val, dict):
        for key in _LABEL_KEYS:
            value = val.get(key)
            if isinstance(value, str) and value:
                return value
    word_id = account.get("word_id")
    return word_id if isinstance(word_id, str) and word_id else None
