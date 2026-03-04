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
cp .env.example .env
```

Edit .env and set at least:

- OPENAI_API_KEY

Optional overrides if you want custom database credentials or ports:

- POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
- AWS_S3_ACCESS_KEY_ID, AWS_S3_SECRET_ACCESS_KEY, AWS_S3_BUCKET

## Start the stack

```bash
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

## Stop the stack

```bash
docker compose down
```
