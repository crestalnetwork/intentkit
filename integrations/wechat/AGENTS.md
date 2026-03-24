# WeChat Integration

Go-based service that connects WeChat messaging to IntentKit's lead agent via the iLink Bot API.

## Architecture

- **Only supports lead agent** (team channels) — does NOT support individual agents
- Polls `team_channels` table for `channel_type='wechat'` entries
- Uses WeChat iLink Bot API (`ilinkai.weixin.qq.com`) for message receiving/sending
- Routes messages to Core API at `POST /core/lead/wechat/execute`

## Directory Structure

- `main.go` — Application entrypoint
- `config/` — Environment configuration
- `ilink/` — WeChat iLink Bot API client (replicated from weclaw project)
- `bot/` — Bot lifecycle manager and message handler
- `api/` — IntentKit Core API client
- `store/` — GORM database models (TeamChannel, TeamChannelData only)

## Environment Variables

- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USERNAME`, `DB_PASSWORD` — PostgreSQL
- `INTERNAL_BASE_URL` — Core API URL (default: `http://intent-api`)
- `WX_NEW_CHANNEL_POLL_INTERVAL` — Sync interval in seconds (default: 10)

## Key Design Notes

- QR code login is handled by the Python API (`app/local/wechat.py`), not this Go service
- This service reads stored credentials from `team_channels.config` and handles message polling
- `context_token` from inbound messages MUST be included when sending replies
- `X-WECHAT-UIN` header uses a random uint32 encoded as base64 per request
