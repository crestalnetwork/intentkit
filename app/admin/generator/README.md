# Agent Generator Package

AI-powered system for generating IntentKit agent schemas from natural language prompts.

## Architecture

```
generator/
├── agent_generator.py    # Main orchestrator
├── skill_processor.py   # Skill identification  
├── validation.py         # Schema validation
├── ai_assistant.py       # AI operations
└── __init__.py          # Package interface
```

## API Usage

### Generate Agent
```bash
curl -X POST "http://localhost:8000/agent/generate" \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "Create a Twitter bot that posts crypto analysis",
       "user_id": "user123"
     }'
```

### Update Existing Agent
```bash
curl -X POST "http://localhost:8000/agent/generate" \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "Add web search capabilities", 
       "existing_agent": {"name": "MyBot", "skills": {}},
       "user_id": "user123"
     }'
```

## Request/Response Format

**Request:**
- `prompt`: Description (10-1000 chars)
- `existing_agent`: Optional agent to update  
- `user_id`: Optional user ID

**Response:**
```json
{
  "name": "GeneratedBot",
  "purpose": "Bot purpose",
  "personality": "Bot personality", 
  "principles": "Bot principles",
  "model": "gpt-4.1-nano",
  "temperature": 0.7,
  "skills": {
    "twitter": {
      "enabled": true,
      "states": {"post_tweet": "public"},
      "api_key_provider": "platform"
    }
  },
  "owner": "user123"
}
```


