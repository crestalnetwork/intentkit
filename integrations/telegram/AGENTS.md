# IntentKit Telegram Integration

This integration reproduces the core Telegram logic using Golang, providing a high-performance and type-safe implementation.

## Tech Stack

- **Language**: Golang (1.23+)
- **Telegram Bot API**: [telego](https://github.com/mymmrac/telego)
- **Database**: [GORM](https://gorm.io/) (PostgreSQL)
- **Logging**: `log/slog` (Standard Library)
- **HTTP Client**: [go-resty/resty](https://github.com/go-resty/resty)
- **Configuration**: Standard environment variables / `.env`

## Architecture

- **`main.go`**: Entrypoint. Initializes DB, Config, and starts the Bot Manager.
- **`store/`**: Database models (`Agent`, `AgentData`) and access layer.
- **`bot/`**:
    - `manager.go`: Manages the lifecycle of bots (syncing with DB, starting/stopping).
    - `handler.go`: Handles incoming Telegram messages and routes them to the Core API.
- **`api/`**: Client for interacting with IntentKit Core API (`/core/execute`).

## usage

### Prerequisites

- PostgreSQL database (shared with IntentKit).
- IntentKit API running (for Core API access).
- Environment variables set (see below).

### Environment Variables

```bash
DATABASE_URL=postgres://user:password@localhost:5432/dbname
CORE_API_URL=http://localhost:8000
TG_NEW_AGENT_POLL_INTERVAL=10 # Seconds
```

### Running
You can run the application directly or using Docker.

#### Direct Execution
```bash
go mod tidy
go run main.go
```

#### Docker
```bash
# Build the image
docker build -t intent-telegram .

# Run the container
docker run -d \
  --name intent-telegram \
  -e DATABASE_URL="postgres://user:password@localhost:5432/intentkit" \
  -e CORE_API_URL="http://host.docker.internal:8000" \
  intent-telegram
```

## Notes

- This integration connects directly to the IntentKit database to read `agents` and `agent_data`.
- It uses the internal `/core/execute` endpoint to process messages.
- Legacy features like "God Bot" and complex filters are intentionally omitted to focus on core logic.
