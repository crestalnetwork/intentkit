# WeChat Integration

Connects a WeChat bot (via the iLink Bot API) to IntentKit team channels.

See [../AGENTS.md](../AGENTS.md) for the common Go stack, layout conventions,
and shared env vars.

## Third-party libs

- WeChat iLink Bot API (`ilinkai.weixin.qq.com`) — proprietary long-polling
  HTTP API; the client is implemented in `ilink/` using resty.

## Channel-specific Env Vars

```bash
# Seconds between DB sync for new/changed wechat channels
WX_NEW_CHANNEL_POLL_INTERVAL=10
```

## Scope

- **Lead agent (team channels) only** — individual agents are not supported.
- Polls `team_channels` where `channel_type='wechat' AND enabled=true`.
- Routes inbound messages to `/core/lead/wechat/execute` in the Core API.

## Key Design Notes

- QR-code login is handled by the Python API (`app/local/wechat.py`), not this
  Go service. This service reads stored credentials from `team_channels.config`.
- `context_token` from an inbound message MUST be echoed back on any reply
  sent to the same user.
- `X-WECHAT-UIN` header is a random `uint32` encoded as base64, regenerated
  per request.
- **CDN uploads** (`ilink.UploadMedia`) use a dedicated resty client with
  `SetAllowNonIdempotentRetry(true)` — POST isn't idempotent in general, but
  the `filekey` is random per call, so replaying is safe.
