---
title: "Docker Compose"
weight: 1
---

## Prerequisites

- Docker and Docker Compose v2
- A server with ports 80 and 443 open
- Domain names for API, frontend, and CDN (e.g., `api.example.com`, `app.example.com`, `cdn.example.com`)

## Setup

Create a directory and download the required files:

```bash
mkdir intentkit && cd intentkit

curl -O https://raw.githubusercontent.com/crestalnetwork/intentkit/main/deployment/docker-compose.yml
curl -O https://raw.githubusercontent.com/crestalnetwork/intentkit/main/deployment/Caddyfile
curl -O https://raw.githubusercontent.com/crestalnetwork/intentkit/main/.env.example
```

## Configure environment

```bash
cp .env.example .env
```

Edit `.env` and configure the required variables:

- `API_DOMAIN` — domain for the API (e.g., `api.example.com`)
- `APP_DOMAIN` — domain for the frontend (e.g., `app.example.com`)
- `CDN_DOMAIN` — domain for static assets (e.g., `cdn.example.com`)
- `TLS_EMAIL` — email for Let's Encrypt certificate registration
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

Visit your frontend domain (e.g., `https://app.example.com`) to confirm everything is working.

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
