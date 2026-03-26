---
title: "Docker Compose"
weight: 1
---

## Prerequisites

- Docker and Docker Compose v2

## Clone the repository

```bash
git clone https://github.com/crestalnetwork/intentkit.git
cd intentkit
```

## Configure environment

```bash
cp .env.example deployment/.env
```

Edit `deployment/.env` and set at least:

- OPENAI_API_KEY

Optional overrides:

- POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
- AWS_S3_ACCESS_KEY_ID, AWS_S3_SECRET_ACCESS_KEY, AWS_S3_BUCKET
- NEXT_PUBLIC_API_BASE_URL (default: http://localhost:8000)
- NEXT_PUBLIC_AWS_S3_CDN_URL (default: http://localhost:9000/static)

## Start the stack

```bash
cd deployment
docker compose up -d
```

## Verify services

```bash
docker compose ps
curl http://localhost:8000/health
```

## Access endpoints

- API: http://localhost:8000
- API docs: http://localhost:8000/redoc
- Frontend: http://localhost:3000
- RustFS S3 endpoint: http://localhost:9000
- RustFS console: http://localhost:9001

## View logs

```bash
# All services
docker compose logs -f

# A specific service
docker compose logs -f api
```

## Update services

After pulling new images:

```bash
docker compose pull
docker compose up -d
```

## Stop the stack

```bash
docker compose down
```

Note: Named volumes (`postgres_data`, `rustfs_data`, `redis_data`) are preserved after stopping. To remove them as well:

```bash
docker compose down -v
```
