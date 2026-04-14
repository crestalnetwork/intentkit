# IntentKit Integrations

Go-based channel adapters that connect external messaging platforms to
IntentKit's Core API.

## Channels

| Channel | Scope | Docs |
|---------|-------|------|
| Telegram | Individual agents + team channels | [telegram/AGENTS.md](./telegram/AGENTS.md) |
| WeChat | Team channels only (lead agent) | [wechat/AGENTS.md](./wechat/AGENTS.md) |

## Tech Stack

- **Language**: Go 1.26+ (module at `integrations/go.mod` covers both channels)
- **HTTP client**: [resty v3](https://resty.dev/) — use it for **all** HTTP
  clients. Retries, timeouts, body-size limits, and SSE are all first-class;
  do **not** hand-roll `net/http` clients. Use `resty.NewEventSource()` for
  SSE streams (see `shared/sse.go`).
- **Database**: [GORM](https://gorm.io/) on PostgreSQL (same DB as the Python
  side; no `ForeignKey` constraints by convention).
- **Logging**: `log/slog` with `slog.NewJSONHandler`.
- **Config**: struct loaded from env via `github.com/hack-fan/config` plus
  `github.com/joho/godotenv` for local `.env` files.

## Layout

```
integrations/
├── AGENTS.md             (this file)
├── cmd/
│   ├── telegram/main.go   # entrypoint
│   └── wechat/main.go     # entrypoint
├── shared/               # cross-channel helpers
│   ├── dispatcher.go      # MessageSender interface, dispatch logic
│   ├── media.go           # DownloadFromURL (resty + SetResponseBodyLimit)
│   └── sse.go             # SSE streaming via resty.EventSource
├── types/                # shared DTOs (ChatMessage, etc.)
├── telegram/             # channel code — see telegram/AGENTS.md
└── wechat/               # channel code — see wechat/AGENTS.md
```

Each channel directory follows the same shape: `api/` (Core API client),
`bot/` (manager + handler + sender), `config/` (env), `store/` (GORM models),
plus any channel-specific subpackage (e.g. `wechat/ilink/`).

## Architecture Pattern

Every channel uses the same skeleton:

1. **Manager** (`bot/manager.go`): on a fixed `time.Ticker`, queries the DB
   for enabled channels/agents. For each new or changed entry, spawns a
   long-poll goroutine; for each removed entry, cancels its context.
2. **Poll/handler loop**: receives incoming messages from the platform,
   forwards them to the Core API (`/core/stream`, `/core/lead/stream`, or a
   channel-specific endpoint), and streams replies back.
3. **Sender** (`bot/sender.go`): implements `shared.MessageSender`. The
   shared dispatcher (`shared/dispatcher.go`) normalizes Core API outputs
   (text / image / video / file / card / choice) to per-channel send calls.

## Conventions

- **HTTP**: always resty. Configure `SetRetryCount` / `SetRetryWaitTime` /
  `SetRetryMaxWaitTime` on the client; never write retry loops by hand. For
  non-idempotent POSTs that are safe to replay, call
  `SetAllowNonIdempotentRetry(true)`. Bound response bodies with
  `SetResponseBodyLimit` instead of `io.LimitReader`.
- **Context**: every outbound call must pass `ctx` via `SetContext(ctx)`.
  Long-running goroutines take `context.WithCancel(context.Background())`
  and cancel on shutdown.
- **Backoff that respects ctx**: poll loops use
  `select { case <-ctx.Done(): ...; case <-time.After(d): ... }` rather
  than raw `time.Sleep`, so they shut down cleanly.
- **Graceful shutdown**: `Manager.Stop()` cancels every per-channel context
  and closes `stopCh`; `cmd/*/main.go` installs SIGTERM/SIGINT handlers.
- **Logging**: use structured slog kv args; include `team_id` / `agent_id`
  in every log line inside per-channel goroutines.

## Common Env Vars

```bash
# Database (shared with IntentKit Python)
DB_HOST=...
DB_PORT=5432
DB_NAME=...
DB_USERNAME=...
DB_PASSWORD=...

# IntentKit Core API
INTERNAL_BASE_URL=http://intent-api

# Observability / runtime
ENV=local
RELEASE=v0.17.x
DEBUG=false
```

Channel-specific env vars live in each channel's `AGENTS.md`.

## Running

```bash
# Directly
go run ./integrations/cmd/telegram
go run ./integrations/cmd/wechat

# Via Docker
docker build -f integrations/Dockerfile.telegram -t intent-telegram integrations/
docker build -f integrations/Dockerfile.wechat   -t intent-wechat   integrations/
```
