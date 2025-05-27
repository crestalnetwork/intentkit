# Agent Generator Service

A service that generates IntentKit agent schemas from natural language prompts using OpenAI's API.

## Overview

The Agent Generator Service analyzes natural language descriptions and generates valid agent schemas with appropriate skills enabled. It can be used to quickly create new agents or update existing ones without manually configuring all the details.

## API Endpoint

```
POST /v1/agent/generate
```

## Request Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | string | Natural language description of the agent's capabilities |
| `update_agent` | boolean | Whether to create/update the agent in the system (default: false) |
| `agent_id` | string | ID of the agent to update (only when update_agent is true) |
| `model_override` | string | Override the default LLM model (supported: gpt-4o-mini, gpt-4.1-nano, gpt-4.1-mini) |
| `temperature_override` | float | Override the default temperature setting (0.0-2.0) |

## Response

```json
{
  "success": true,
  "agent_schema": {
    "name": "Agent name",
    "purpose": "Agent purpose...",
    "personality": "Agent personality...",
    "principles": "Agent principles...",
    "skills": {
      "skill_name": {
        "enabled": true,
        "states": {
          "state_name": "public"
        }
      }
    },
    "model": "gpt-4.1-nano",
    "temperature": 0.7,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0
  },
  "agent_id": "created-or-updated-agent-id",
  "identified_skills": ["skill_name1", "skill_name2"]
}
```

## Example Requests

### 1. Generate a Web Search Agent Schema

```bash
curl -X POST http://localhost:8000/v1/agent/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create an agent that can search the web for information and provide detailed answers",
    "update_agent": false
  }'
```

Expected skills: `tavily`

### 2. Generate a Crypto Twitter Bot

```bash
curl -X POST http://localhost:8000/v1/agent/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a Twitter bot that posts daily updates about cryptocurrency prices",
    "update_agent": true,
    "model_override": "gpt-4.1-nano",
    "temperature_override": 0.5
  }'
```

Expected skills: `twitter`, `cryptocompare`

### 3. Generate a DeFi Research Assistant

```bash
curl -X POST http://localhost:8000/v1/agent/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "I need an assistant that can analyze DeFi protocols, track TVL, and search for information about new projects",
    "update_agent": true
  }'
```

Expected skills: `defillama`, `tavily`, `dexscreener`

### 4. Generate a Portfolio Tracker

```bash
curl -X POST http://localhost:8000/v1/agent/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create an agent that can track my crypto portfolio, check prices, and analyze my investments",
    "update_agent": false
  }'
```

Expected skills: `portfolio`, `cryptocompare`

### 5. Update an Existing Agent

```bash
curl -X POST http://localhost:8000/v1/agent/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Update my agent to add web search capabilities and the ability to post on Twitter",
    "update_agent": true,
    "agent_id": "existing-agent-id"
  }'
```

Expected skills: `tavily`, `twitter`

## Implementation Details

The service uses:

1. **Keyword Matching**: First attempts to match skills using a predefined mapping of keywords to skills
2. **OpenAI Analysis**: For more complex prompts, uses OpenAI to analyze and identify appropriate skills
3. **Schema Generation**: Creates complete agent schemas with name, purpose, personality, principles, and skills

## Environment Variables

- `OPENAI_API_KEY`: Required for OpenAI API calls

## Supported Skills

The service supports all IntentKit skills, including:
- Web search (tavily)
- Social media (twitter, slack, telegram)
- Cryptocurrency (cryptocompare, cryptopanic)
- DeFi (defillama, dexscreener)
- Blockchain analytics (dune_analytics, dapplooker)
- And many more

## Error Handling

The API provides clear error messages for:
- Missing OpenAI API key
- Invalid model selections
- Schema validation errors
- Agent creation/update failures 