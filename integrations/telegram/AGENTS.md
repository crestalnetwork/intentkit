# Telegram Integration

Connects Telegram bots to IntentKit. Supports both individual agents and team
channels.

See [../AGENTS.md](../AGENTS.md) for the common Go stack, layout conventions,
and shared env vars.

## Third-party libs

- [telego](https://github.com/mymmrac/telego) — Telegram Bot API client
- [redis/go-redis/v9](https://github.com/redis/go-redis) — session / cache

## Channel-specific Env Vars

```bash
# Seconds between DB sync for new/changed agents
TG_NEW_AGENT_POLL_INTERVAL=10

# Redis (rate limiting / session state)
REDIS_HOST=...
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
```

## Notes

- Reads both `agents` / `agent_data` (individual agents) **and** `team_channels`
  (team-level bots).
- Routes individual-agent messages to `/core/stream`; team-channel messages to
  `/core/lead/stream`.
- Legacy features from the Python implementation ("God Bot", complex filters)
  are intentionally omitted.
