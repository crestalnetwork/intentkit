---
title: "Docker Swarm"
weight: 2
---

## Prerequisites

- Docker with Swarm mode enabled
- At least one node in the swarm cluster

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

## Initialize swarm

Skip this step if you already have a swarm cluster.

```bash
docker swarm init
```

## Label the node for stateful services

Stateful services (PostgreSQL, Redis, RustFS) use volume mounts for data persistence. They must always run on the same node to avoid data loss. Label the node that should host these services:

```bash
# List nodes to find the node name/ID
docker node ls

# Add the stateful label to your chosen node
docker node update --label-add stateful=true <node-name>
```

In a single-node setup, label that node. In a multi-node cluster, pick a node with sufficient storage.

## Deploy the stack

```bash
cd deployment
docker stack deploy -c docker-stack.yml intentkit
```

## Verify services

```bash
# List all services and their status
docker service ls

# Check a specific service's logs
docker service logs intentkit_api

# Health check
curl http://localhost:8000/health
```

## Access endpoints

- API: http://localhost:8000
- API docs: http://localhost:8000/redoc
- Frontend: http://localhost:3000
- RustFS S3 endpoint: http://localhost:9000
- RustFS console: http://localhost:9001

## Scale services

```bash
# Scale API replicas
docker service scale intentkit_api=3

# Scale frontend replicas
docker service scale intentkit_frontend=2
```

## Update services

After pulling new images:

```bash
# Update a single service
docker service update --image crestal/intentkit:latest intentkit_api

# Or redeploy the entire stack (picks up all changes)
docker stack deploy -c docker-stack.yml intentkit
```

The API and frontend services are configured with `order: start-first` rolling updates, so new containers start before old ones are removed.

## Remove the stack

```bash
docker stack rm intentkit
```

Note: Named volumes (`postgres_data`, `rustfs_data`, `redis_data`) are preserved after removal. To delete them:

```bash
docker volume rm intentkit_postgres_data intentkit_rustfs_data intentkit_redis_data
```
