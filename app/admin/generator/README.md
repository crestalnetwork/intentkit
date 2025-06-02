# Agent Generator Package

AI-powered system for generating IntentKit agent schemas from natural language prompts with project-based conversation history.

## Architecture

```
generator/
├── agent_generator.py    # Main orchestrator
├── skill_processor.py   # Skill identification  
├── validation.py         # Schema validation
├── ai_assistant.py       # AI operations + conversation history
├── llm_logger.py         # Individual LLM call tracking
└── __init__.py          # Package interface
```

## API Usage

### Generate New Agent
```bash
curl -X POST "http://localhost:8000/agent/generate" \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "Create a Twitter bot that posts crypto analysis",
       "user_id": "user123"
     }'
```

### Generate Agent with Project Context
```bash
curl -X POST "http://localhost:8000/agent/generate" \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "Now add web search capabilities for research",
       "user_id": "user123",
       "project_id": "existing_project_id"
     }'
```

### Update Existing Agent
```bash
curl -X POST "http://localhost:8000/agent/generate" \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "Change the name to CryptoBot Pro", 
       "existing_agent": {"name": "MyBot", "skills": {}},
       "user_id": "user123"
     }'
```

## Request/Response Format

**Request:**
- `prompt`: Description (10-1000 chars)
- `existing_agent`: Optional agent to update  
- `user_id`: Optional user ID
- `project_id`: Optional project ID for conversation history

**Response:**
```json
{
  "agent": {
    "name": "CryptoBot",
    "purpose": "Automated crypto analysis and posting",
    "personality": "Professional and analytical", 
    "principles": "• Provide accurate analysis\n• Post regularly\n• Stay updated",
    "model": "gpt-4.1-nano",
    "temperature": 0.7,
    "skills": {
      "twitter": {
        "enabled": true,
        "states": {"post_tweet": "public"},
        "api_key_provider": "platform"
      },
      "tavily": {
        "enabled": true,
        "states": {"search": "public"},
        "api_key_provider": "platform"
      }
    },
    "owner": "user123"
  },
  "project_id": "bkj49k3nt2hc73jbdnp0",
  "summary": "Congratulations! You've successfully created CryptoBot, an AI agent that can analyze cryptocurrency trends and post insights on Twitter. Your agent is ready to help you stay on top of the crypto market with automated research and social media engagement!"
}
```

## Project Conversation History

The system maintains conversation history per project_id:

1. **First Request**: Creates new project_id if not provided
2. **Subsequent Requests**: Use same project_id to maintain context
3. **LLM Context**: Previous conversations guide new generations
4. **Conversation Flow**: 
   - System prompt
   - User message 1 → AI response 1
   - User message 2 → AI response 2
   - Current user message

This enables iterative agent refinement with context awareness.



