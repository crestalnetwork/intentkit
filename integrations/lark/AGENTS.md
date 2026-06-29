# Lark / Feishu Integration

Connects Lark (international) / Feishu (China) to IntentKit team channels as a
**single ISV (store) app**: each team authorizes the one official app for *its
own* enterprise, and one public webhook serves every tenant, routed by
`tenant_key`.

See [../AGENTS.md](../AGENTS.md) for the common Go stack and conventions.

## Architecture (multi-tenant ISV, one app)

```
team admin ─"Authorize"▶ Lark auth ─redirect▶ SPA /oauth/callback (admin's session)
                                              └▶ POST Python /lead/oauth/complete  (authed)
                                                 verify admin + state, then ▼ (internal, secret)
                                              ┌──────────────────────────────┘
this service /lark/exchange ◀────────────────┘  code → tenant_key, store on team's lark row
this service /lark/push      ◀── Python push ─── proactive send for a tenant
Lark tenant events ─HTTPS POST▶ this service /lark/events
                                SDK decrypts + verifies → resolve team by tenant_key
                                → forward to lead → reply with that tenant's token
```

- A **single marketplace (ISV) SDK client** serves every tenant. The SDK
  auto-manages the `app_ticket → app_access_token → tenant_access_token` chain
  (it captures the app_ticket Lark pushes to the webhook) and sends each request
  with `larkcore.WithTenantKey(tenant_key)`.
- **OAuth completion is SPA-confirmed and session-bound.** The provider redirects
  to the SPA, which relays `code`+`state` to the Python API's authenticated
  `/lead/oauth/complete` (gated by the admin's JWT; team + channel ride the
  signed state). Python verifies the admin-bound `state`, then calls this
  service's **internal** `/lark/exchange`
  (the code→tenant_key swap needs the SDK token chain, which only lives here).
- The two reverse endpoints `/lark/exchange` and `/lark/push` are **internal
  only**: the listen port is public (Lark posts events), so they require the
  shared `X-Internal-Secret` header (`LARK_INTERNAL_SECRET`) and fail closed when
  it's unset.
- Per-team install state on `team_channels.config` for the team's `lark` row:
  `{tenant_key}`. Inbound events resolve the owning team via `config.tenant_key`.

## Third-party libs

- [oapi-sdk-go/v3](https://github.com/larksuite/oapi-sdk-go) — the event
  `dispatcher` decrypts (AES), verifies, answers the url_verification handshake,
  and captures the app_ticket; we wire it to an HTTP handler instead of a
  WebSocket. The marketplace `lark.Client` handles the token chain.

## Security (review these)

- **Event auth** is handled by the SDK dispatcher
  (`NewEventDispatcher(verificationToken, encryptKey)`): it AES-decrypts the body
  and verifies the verification token before any handler runs.
- **OAuth `state`** is now verified in the Python API only
  (`oauth.py::verify_state`), bound to the initiating admin (`team_id` +
  `user_id`); the completion endpoint additionally re-checks the admin's session
  (`verify_team_admin`). Go no longer verifies state — it trusts the
  secret-gated internal call.
- **Internal endpoints** (`/lark/exchange`, `/lark/push`) are gated by
  `LARK_INTERNAL_SECRET` (constant-time compare, `bot/internal.go`).

## Channel-specific Env Vars

```bash
# Go webhook service
LARK_APP_ID=cli_xxx
LARK_APP_SECRET=xxx
LARK_ENCRYPT_KEY=...               # AES key to decrypt events
LARK_VERIFICATION_TOKEN=...        # verifies events are from Lark
LARK_DOMAIN=feishu                 # feishu | lark
LARK_LISTEN_ADDR=:8084             # public events webhook + internal exchange/push
LARK_INTERNAL_SECRET=...           # shared; gates /lark/exchange + /lark/push

# Python API
LARK_APP_ID=cli_xxx                # same app id
LARK_DOMAIN=feishu
OAUTH_STATE_SECRET=...             # signs the admin-bound install state
LARK_SERVICE_URL=http://<lark-service-host>:8084     # reverse calls to this service
LARK_INTERNAL_SECRET=...           # same secret as the Go service
```

The OAuth redirect is derived as `${APP_BASE_URL}/oauth/callback` (no separate
var); the events webhook lives under `${API_BASE_URL}`.

## Console setup (one ISV/store app)

1. Create a store app in the Lark/Feishu developer console.
2. **Security Settings** → set the Encrypt Key + Verification Token (into the env
   above).
3. **Event Subscription** → "Send to developer server", URL =
   `${API_BASE_URL}/lark/events`. Subscribe to `im.message.receive_v1`
   (and card actions). The app_ticket event is handled automatically.
4. **Permissions / redirect** → add `${APP_BASE_URL}/oauth/callback` as an OAuth
   redirect.
5. Publish so tenants can install; teams click "Authorize Lark" in the UI.

## UX: interactive cards

Replies use Feishu interactive cards (`larkclient/card.go`), unchanged: agent
text → markdown card; choices → buttons (card.action.trigger callbacks); cards →
header + body + cover image + link button. Every rich path falls back to text.

## Key Design Notes

- One webhook serves all tenants; there are **no per-team connections** and no
  WebSocket long connection.
- Inbound media is downloaded via the message-resource API (with the tenant's
  token), re-hosted on S3, and forwarded as attachments. Voice is forwarded
  as-is (Opus).
- `/default` in a chat makes it the team's proactive-push target.
- **Proactive push** routes through this service's `/lark/push` (Python →
  `_send_lark` → here → tenant-bound `SendText`), reusing the SDK token chain.
