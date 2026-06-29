# Slack Integration

Connects Slack to IntentKit team channels as a **single distributed OAuth app**:
each team installs the one official app into *its own* workspace ("Add to
Slack"), and one public webhook serves every workspace, routed by workspace id.

See [../AGENTS.md](../AGENTS.md) for the common Go stack and conventions.

## Architecture (multi-tenant, one app)

```
team admin ─"Add to Slack"▶ Slack OAuth ─redirect▶ SPA /oauth/callback (admin's session)
                                                   └▶ POST Python /lead/oauth/complete (authed)
                                                      verify admin + state → exchange code →
                                                      store {workspace_id, bot_token} on slack row
Slack workspace events ──HTTPS POST──▶ Go webhook (this service)
                                       verify signature → resolve team by workspace_id
                                       → forward to lead → reply with that workspace's token
```

- **OAuth install + completion** live in the **Python API** (`app/team` +
  `intentkit/core/team/oauth.py`) and own token storage. Completion is
  **SPA-confirmed and session-bound**: Slack redirects to the SPA, which relays
  `code`+`state` to the authenticated `/lead/oauth/complete` endpoint (team +
  channel ride the signed state). The `state` is HMAC-signed and bound to the
  initiating admin (`team_id` + `user_id`), and completion re-checks the admin's
  session + role — so a phished install link can't bind a victim's workspace to
  the attacker's team.
- **Event/interaction webhook** lives **here in Go** (`bot/webhook.go`) — it
  reuses the Block Kit sender / media code. It is the only new public surface.
- Per-team install state is stored on `team_channels.config` for the team's
  `slack` row: `{workspace_id, bot_token, workspace_name, bot_user_id}`. Inbound
  events resolve the owning team via `config.workspace_id`; replies use
  `bot_token`.

## Third-party libs

- [slack-go/slack](https://github.com/slack-go/slack) — used for the Web API
  client (sending) and Block Kit types. The webhook + signature verification are
  hand-rolled (`net/http` + `crypto/hmac`); the rule "use resty for all HTTP"
  doesn't apply to the vendored SDK or to the inbound webhook server.

## Security (review these)

- **`bot/webhook.go::verifySlackSignature`** — the inbound trust boundary. Every
  request is authenticated by the app **signing secret** (HMAC-SHA256 over
  `v0:{timestamp}:{body}`, constant-time compare) and rejected if the timestamp
  is older/newer than 5 min (replay protection). Covered by `webhook_test.go`.
- **`intentkit/core/team/oauth.py::verify_state`** — the OAuth CSRF /
  session-binding guard. `state` is an HMAC-signed `team_id:channel:user_id:
  timestamp`; completion acts only on a valid, fresh state whose `team_id` /
  `user_id` match the authenticated admin (`verify_team_admin`).

## Channel-specific Env Vars

```bash
# Go webhook service
SLACK_SIGNING_SECRET=...          # verify inbound webhooks
SLACK_LISTEN_ADDR=:8083           # public Events/interactions webhook (behind ingress/TLS)

# Python API (OAuth)
SLACK_CLIENT_ID=...
SLACK_CLIENT_SECRET=...
SLACK_OAUTH_SCOPES=chat:write,channels:history,groups:history,im:history,app_mentions:read,files:read,files:write,users:read
OAUTH_STATE_SECRET=...            # shared; signs the OAuth state
```

The OAuth redirect is derived as `${APP_BASE_URL}/oauth/callback` (no separate
var); the events/interactions webhooks live under `${API_BASE_URL}`.

## Console setup (one distributed app)

1. Create a Slack app, enable **distribution** (so other workspaces can install).
2. **OAuth & Permissions** → Redirect URL = `${APP_BASE_URL}/oauth/callback` (the
   SPA landing page). Add the bot scopes above.
3. **Event Subscriptions** → enable, Request URL = `${API_BASE_URL}/slack/events`
   (this Go service). Subscribe to bot events `message.im`, `app_mention`
   (optionally `message.channels`/`groups`/`mpim`).
4. **Interactivity & Shortcuts** → enable, Request URL =
   `${API_BASE_URL}/slack/interactions`.
5. Copy the **Signing Secret** + **Client ID/Secret** into the env above.
6. Teams click "Add to Slack" in the IntentKit UI to install into their workspace.

## UX: Block Kit

Replies use Block Kit (`slackclient/blocks.go`), unchanged from before: agent
text → native `markdown` block; choices → buttons (`block_actions`); cards →
header + body + image + link button; long replies split across markdown blocks.
Every rich path falls back to plain text.

## Key Design Notes

- One webhook serves all workspaces; there are **no per-team connections** and no
  Socket Mode. The Web API client is built per request from the resolved
  workspace bot token.
- slack-go's `MessageEvent` omits the top-level `files` array, so inbound files
  are parsed from the raw webhook body, downloaded with the workspace bot token,
  re-hosted on S3, and forwarded as attachments.
- Outbound media uses the external-upload flow (`files.getUploadURLExternal` →
  PUT → `files.completeUploadExternal`).
- `/default` in a chat makes it the team's proactive-push target.
- Proactive pushes (`intentkit/core/team/push.py::_send_slack`) use the team's
  stored workspace `bot_token`.
