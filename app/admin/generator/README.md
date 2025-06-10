# Agent Generator Package

AI-powered system for generating IntentKit agent schemas from natural language prompts with project-based conversation history and automatic tag generation.

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

### Get Chat History - All Projects for User
```bash
curl -X GET "http://localhost:8000/agent/chat-history?user_id=user123&limit=20"
```

### Get Chat History - Specific Project
```bash
curl -X GET "http://localhost:8000/agent/chat-history?project_id=bkj49k3nt2hc73jbdnp0&user_id=user123"
```

### Get Chat History - Specific Project (No User Validation)
```bash
curl -X GET "http://localhost:8000/agent/chat-history?project_id=bkj49k3nt2hc73jbdnp0"
```

### Get All Recent Projects (No User Filter)
```bash
curl -X GET "http://localhost:8000/agent/chat-history?limit=10"
```

## Request/Response Format

**Agent Generation Request:**
- `prompt`: Description (10-1000 chars)
- `existing_agent`: Optional agent to update  
- `user_id`: Optional user ID
- `project_id`: Optional project ID for conversation history

**Agent Generation Response:**
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
  "summary": "Congratulations! You've successfully created CryptoBot...",
  "tags": [{"id": 3}, {"id": 11}, {"id": 25}]
}
```

**Chat History Response:**
```json
{
  "projects": [
    {
      "project_id": "bkj49k3nt2hc73jbdnp0",
      "user_id": "user123",
      "created_at": 1703123456.789,
      "last_activity": 1703123556.789,
      "message_count": 4,
      "first_message": {
        "role": "user",
        "content": "Create a Twitter bot that posts crypto analysis"
      },
      "last_message": {
        "role": "assistant", 
        "content": "I've created CryptoBot with Twitter and research capabilities..."
      },
      "conversation_history": [
        {"role": "user", "content": "Create a Twitter bot..."},
        {"role": "assistant", "content": "I've created..."},
        {"role": "user", "content": "Now add web search..."},
        {"role": "assistant", "content": "I've updated..."}
      ]
    }
  ]
}
```

## Testing the Chat History API

1. **Create an Initial Agent (Get Project ID)**
```bash
curl -X POST "http://localhost:8000/agent/generate" \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "Create a trading bot for crypto analysis",
       "user_id": "test_user_123"
     }'
```
*Save the `project_id` from the response for next steps*

2. **Continue Conversation (Use Same Project ID)**
```bash
curl -X POST "http://localhost:8000/agent/generate" \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "Add social media posting capabilities",
       "user_id": "test_user_123", 
       "project_id": "YOUR_PROJECT_ID_FROM_STEP_1"
     }'
```

3. **Get All Projects for User**
```bash
curl -X GET "http://localhost:8000/agent/chat-history?user_id=test_user_123"
```

4. **Get Specific Project Conversation**
```bash
curl -X GET "http://localhost:8000/agent/chat-history?project_id=YOUR_PROJECT_ID&user_id=test_user_123"
```

5. **Test Access Control (Should Return 404)**
```bash
curl -X GET "http://localhost:8000/agent/chat-history?project_id=YOUR_PROJECT_ID&user_id=different_user"
```

### API Response Modes

**Mode 1: All Projects for User** (`user_id` only)
- Returns: List of all projects for the user
- Sorted by: Last activity (most recent first)
- Includes: Full conversation history for each project

**Mode 2: Specific Project** (`project_id` provided)
- Returns: Single project with full conversation history
- Access Control: Validates `user_id` matches project owner (if provided)
- Error: 404 if project not found or access denied

### Expected Response Structure

**All Projects Response:**
```json
{
  "projects": [
    {
      "project_id": "bkj49k3nt2hc73jbdnp0",
      "user_id": "test_user_123",
      "created_at": 1703123456.789,
      "last_activity": 1703123556.789,
      "message_count": 4,
      "conversation_history": [...]
    }
  ]
}
```

**Specific Project Response:**
```json
{
  "projects": [
    {
      "project_id": "bkj49k3nt2hc73jbdnp0", 
      "user_id": "test_user_123",
      "created_at": 1703123456.789,
      "last_activity": 1703123556.789,
      "message_count": 4,
      "first_message": {"role": "user", "content": "..."},
      "last_message": {"role": "assistant", "content": "..."},
      "conversation_history": [
        {"role": "user", "content": "Create a trading bot..."},
        {"role": "assistant", "content": "I've created..."},
        {"role": "user", "content": "Add social media..."},
        {"role": "assistant", "content": "I've updated..."}
      ]
    }
  ]
}
```

## Features

### Project Conversation History

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

### Automatic Tag Generation

The system automatically generates exactly 3 relevant tags using Nation API + LLM selection. Always returns 3 tags, never empty.

### Chat History Management

Track and retrieve conversation history across projects:

1. **User-Specific History**: Filter projects by user_id
2. **Project Metadata**: Stores creation time, last activity, user association
3. **Conversation Tracking**: Complete message history for each project
4. **Recent Activity**: Sorted by last activity for easy access