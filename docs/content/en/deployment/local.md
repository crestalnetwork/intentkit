---
title: "Local Preview"
weight: 0
---

Run IntentKit locally for a quick preview and evaluation.

## Prerequisites

### Install Docker (macOS)

```bash
brew update
brew install colima docker-compose docker-buildx
```

For Docker to find the plugins, add `cliPluginsExtraDirs` to `~/.docker/config.json`:

```json
{
  "cliPluginsExtraDirs": [
    "/opt/homebrew/lib/docker/cli-plugins"
  ]
}
```

Start the Docker runtime:

```bash
colima start
```

For other operating systems, please install Docker and Docker Compose following the official documentation.

## Setup

Clone the repository:

```bash
git clone https://github.com/crestalnetwork/intentkit.git
cd intentkit
```

## Configure environment

```bash
cp .env.example .env
```

Edit `.env` and configure at least one LLM provider API key (e.g., `OPENAI_API_KEY`).

For local preview, you can leave `APP_DOMAIN`, `TLS_EMAIL`, and auth settings empty — the defaults are already set for local development.

## Start the stack

```bash
docker compose up -d
```

## Verify

Check that all containers are running:

```bash
docker compose ps
```

Check the logs for errors:

```bash
docker compose logs -f
```

Visit `http://localhost:3000` to confirm everything is working.

## Stop the stack

```bash
docker compose down
```

Note: Named volumes are preserved after stopping. To remove them as well:

```bash
docker compose down -v
```
