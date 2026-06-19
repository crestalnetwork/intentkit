# Lark / Feishu Integration

Connects a Lark (international) or Feishu (China) bot to IntentKit team
channels. A single `lark` channel type serves both platforms — `config.domain`
(`feishu` | `lark`) selects the open-platform host.

See [../AGENTS.md](../AGENTS.md) for the common Go stack, layout conventions,
and shared env vars.

## Third-party libs

- [oapi-sdk-go/v3](https://github.com/larksuite/oapi-sdk-go) — official Lark/
  Feishu SDK. Used for both the REST client (`lark.Client`) and the WebSocket
  long-connection client (`ws.Client`). Like telegram's `telego`, this is a
  vendored platform SDK with its own HTTP client, so the "use resty for all
  HTTP" rule does not apply to it.

## Transport — WebSocket long connection

Unlike a webhook bot, this service does **not** expose a public callback URL.
Each enabled team channel opens an outbound WebSocket long connection
(`ws.Client.Start`) over which Lark pushes events. This keeps the same
"outbound connection, no public ingress" shape as the wechat/telegram
long-pollers; the manager just maintains a WebSocket per team instead of a poll
loop. Requires a **custom app** (自建应用) with *Event & Callback → Long
Connection* mode enabled.

## Scope

- **Lead agent (team channels) only** — individual agents are not supported.
- Polls `team_channels` where `channel_type='lark' AND enabled=true`.
- Routes inbound messages to `/core/lead/stream` with `channel_type=lark`.
- No per-channel runtime state: Lark has no reply-window restriction, so
  (unlike wechat) there is no session timer, typing ticket, or context token,
  and no `team_channel_data` row. Proactive pushes (`intentkit/core/team/
  push.py::_send_lark`) authenticate with the app credentials directly.

## Channel-specific Env Vars

```bash
# Seconds between DB sync for new/changed lark channels
LK_NEW_CHANNEL_POLL_INTERVAL=10
```

Per-team credentials live in `team_channels.config`:

```json
{ "app_id": "cli_xxx", "app_secret": "xxx", "domain": "feishu" }
```

## UX: interactive cards

Lark replies lean on interactive message cards rather than plain text:

- **Agent text** renders as a markdown card, so LLM markdown (bold, lists,
  code, links) displays natively instead of as raw syntax.
- **Choices** (`choice` attachments) render as real buttons. A click fires a
  `card.action.trigger` callback (delivered over the same long connection) that
  the handler forwards to the lead agent as the user's reply — a port of the
  telegram inline-button paradigm. Each button also carries its option text, so
  a user who simply types the option still works; the buttons degrade
  gracefully.
- **Cards** (`card` attachments) render with a coloured header, markdown body,
  optional cover image, and a link button.

Every rich path falls back to plain text if the card/upload fails, so a reply
is never silently dropped.

## Key Design Notes

- `channel_user_id` is the sender's `open_id` (binds to `users.lark_id`);
  `chat_id` is the Lark chat id (`oc_…`), used both for routing and for
  replies (`receive_id_type=chat_id`).
- Inbound media (image / file / audio / video / rich-text `post`) is downloaded
  via the message-resource API, re-hosted on S3, and forwarded as attachments.
  Voice messages are forwarded as-is (Lark sends Opus); unlike the wechat
  channel's SILK→MP3 step there is no transcode, so downstream model support
  for Opus audio varies — transcoding is a possible future enhancement.
- `/default` in a chat makes it the team's proactive-push target.
- The SDK reconnects internally (`WithAutoReconnect`); the manager's per-team
  loop only re-establishes after a fatal return (e.g. bad credentials) with
  bounded backoff, and feeds the shared outage tracker for alerting.
