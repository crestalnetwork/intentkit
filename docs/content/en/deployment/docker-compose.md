---
title: "Docker Compose"
weight: 1
---

## Prerequisites

- Docker and Docker Compose v2
- A server with ports 80 and 443 open
- A domain name for the application (e.g., `app.example.com`)

## Setup

Create a directory and download the required files:

```bash
mkdir intentkit
cd intentkit
```

```bash
curl -O https://raw.githubusercontent.com/crestalnetwork/intentkit/main/deployment/docker-compose.yml
curl -O https://raw.githubusercontent.com/crestalnetwork/intentkit/main/deployment/caddy-entrypoint.sh
curl -O https://raw.githubusercontent.com/crestalnetwork/intentkit/main/.env.example

chmod +x caddy-entrypoint.sh
```

## Configure environment

```bash
cp .env.example .env
```

Edit `.env` and configure the required variables:

- `APP_DOMAIN` — domain for the application (e.g., `app.example.com`)
- `TLS_EMAIL` — email for Let's Encrypt certificate registration
- `BASIC_AUTH_USER` — username for basic auth (leave empty to disable)
- `BASIC_AUTH_PASSWORD` — password for basic auth (leave empty to disable)
- `OPENAI_API_KEY` — your OpenAI API key

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

Visit your domain (e.g., `https://app.example.com`) to confirm everything is working.

## Update services

```bash
docker compose pull
docker compose up -d
```

## Stop the stack

```bash
docker compose down
```

Note: Named volumes are preserved after stopping. To remove them as well:

```bash
docker compose down -v
```
