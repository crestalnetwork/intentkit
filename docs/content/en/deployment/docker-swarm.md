---
title: "Docker Swarm"
weight: 2
---

## Prerequisites

- Docker with Swarm mode enabled

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

Optional overrides:

- POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
- AWS_S3_ACCESS_KEY_ID, AWS_S3_SECRET_ACCESS_KEY, AWS_S3_BUCKET

## Initialize swarm and deploy

```bash
docker swarm init
docker stack deploy -c docs/deployment/docker-compose.yml intentkit
```

## Check services

```bash
docker service ls
```

## Access endpoints

- API: http://localhost:8000
- API docs: http://localhost:8000/redoc
- RustFS S3 endpoint: http://localhost:9000
- RustFS console: http://localhost:9001
