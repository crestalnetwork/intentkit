---
title: "Introduction"
cascade:
  type: docs
  sidebar:
    open: true
---

IntentKit is an open-source, self-hosted cloud agent cluster that manages a collaborative team of AI agents. Unlike local-first agent frameworks that demand expensive hardware and broad system permissions, IntentKit takes a cloud-native approach — lightweight, always-on, and production-ready out of the box.

## What IntentKit Does

IntentKit lets you create, configure, and run multiple AI agents that work together as a team. Each agent can:

- Interact with users through social platforms such as Twitter and Telegram
- Execute tasks autonomously on a schedule
- Call other agents for collaboration
- Use an extensible skill system to perform actions — from web searches to on-chain transactions

All of this runs as a set of standard containerized services (API server, autonomous runner, and scheduler) backed by PostgreSQL, Redis, and S3-compatible storage.

## Key Features

- **Cloud-Native** — Designed for container orchestration. Runs efficiently with minimal resources.
- **Collaborative Agents** — Agents can invoke each other, enabling multi-agent workflows.
- **Extensible Skill System** — Add new capabilities by writing skill plugins without modifying the core.
- **Platform Integrations** — Built-in support for Twitter, Telegram, and more.
- **Crypto-Friendly** — Optional Web3 and blockchain integrations for on-chain operations.
- **API-First** — Every agent exposes its own API for external integration.

## About This Documentation

This documentation covers how to deploy and use IntentKit. You will find:

- **Deployment** — Step-by-step guides for running IntentKit with Docker Compose (development) or Docker Swarm (production).
- **Usage** — How to create agents, configure skills, and interact with the system.
- **Others** — Architecture details, API reference, LLM configuration, and contribution guidelines.
