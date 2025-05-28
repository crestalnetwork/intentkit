# Agent Generator

It takes your plain English description and automatically creates a complete agent with the right skills enabled. No more manual configuration, just describe what you want and let the AI do the work.

## Quick Start

**Generate an agent:**
```bash
POST /v1/agent/generate
{
  "prompt": "Create a Twitter bot that posts crypto price updates",
  "update_agent": true
}
```

**Validate an existing agent:**
```bash
GET /v1/agent/validate?agent_id=my-agent
```

## API Reference

### POST /v1/agent/generate

Takes your description and builds a complete agent schema.

**Parameters:**
- `prompt` (string, required) - Describe what you want (10-1000 chars)
- `update_agent` (boolean) - Actually create the agent? (default: false)
- `agent_id` (string) - Update existing agent instead of creating new one
- `model_override` (string) - Use different AI model (gpt-4.1-nano, gpt-4.1-mini, gpt-4o-mini)
- `temperature_override` (float) - Control creativity (0.0-2.0)

**Response:**
```json
{
  "success": true,
  "agent_schema": { /* complete agent config */ },
  "agent_id": "your-new-agent-id",
  "identified_skills": ["twitter", "cryptocompare"],
  "schema_validation": {
    "schema_valid": true,
    "agent_valid": true
  }
}
```

### GET /v1/agent/validate

Check if an agent's configuration is valid.

**Parameters:**
- `agent_id` (string, required) - Which agent to check

## Writing Good Prompts

### ✅ Good Examples
- "Create a crypto portfolio tracker that monitors prices and sends alerts"
- "Build a research assistant that searches the web and summarizes findings"
- "Make a Twitter bot that posts daily DeFi market analysis"

### ❌ Avoid These
- "agent" (too short)
- "Create an agent that does everything..." (too vague)
- Super long descriptions with lots of repetition

### Pro Tips
- **Be specific**: Say exactly what you want the agent to do
- **Mention data sources**: Web search, crypto data, social media, etc.
- **Keep it focused**: 50-300 characters usually works best
- **Include behavior**: How should the agent act or respond?

## How It Works

1. **Skill Detection**: AI analyzes your prompt to identify needed capabilities
2. **Schema Generation**: Creates complete agent config with name, purpose, personality
3. **Validation**: Checks everything against IntentKit's requirements
4. **Agent Creation**: Optionally creates/updates the actual agent

## Supported Skills

The generator knows about all IntentKit skills:
- **Web & Research**: tavily (web search)
- **Social Media**: twitter, slack, telegram
- **Crypto Data**: cryptocompare, cryptopanic, defillama, dexscreener
- **Analytics**: dune_analytics, dapplooker
- **And many more!**

## Examples

### Web Search Agent
```json
{
  "prompt": "Create an agent that can search the web and provide detailed answers",
  "update_agent": true
}
```

### Crypto Twitter Bot
```json
{
  "prompt": "Make a Twitter bot that posts daily crypto price updates",
  "update_agent": true,
  "model_override": "gpt-4.1-nano"
}
```

### Portfolio Tracker 
```json
{
  "prompt": "I need an agent that tracks my crypto portfolio and analyzes investments",
  "update_agent": false
}
```
