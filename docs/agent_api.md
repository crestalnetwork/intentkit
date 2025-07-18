# Agent API Intro

This guide teaches LLMs how to interact with IntentKit agent APIs when building applications. The agent API provides endpoints to create chat threads, send messages, and retrieve conversation history.

## Base URL and Authentication

All API endpoints are prefixed with `/v1/` and require authentication using a Bearer token.

**Base URL:** `http://localhost:8000/v1/` when local development. For production, you will get it when you get the key.

**Authentication:** Include the agent token in the Authorization header:
```
Authorization: Bearer <your_agent_token>
```
## How to Get the API Key

IntentKit provides system skills for managing agent API keys. Active the skills in agent, and let it give you the API Keys. You can get two types of API keys with different access levels:

- **Private API Key (sk-)**: Can access all skills (public and owner-only)
- **Public API Key (pk-)**: Can only access public skills

## Quick Start Example

Here's a complete example showing how to create a thread, send a message, and list messages:

### 1. Create a Chat Thread

```bash
curl -X POST "http://localhost:8000/v1/chats" \
  -H "Authorization: Bearer <your_agent_token>" \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "id": "chat_123456",
  "agent_id": "agent_789",
  "user_id": "agent_789_user123",
  "summary": "",
  "rounds": 0,
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z"
}
```

### 2. Send a Message

```bash
curl -X POST "http://localhost:8000/v1/chats/chat_123456/messages" \
  -H "Authorization: Bearer <your_agent_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, how can you help me today?",
    "user_id": "user123"
  }'
```

**Response:**
```json
[
  {
    "id": "msg_user_001",
    "agent_id": "agent_789",
    "chat_id": "chat_123456",
    "user_id": "agent_789_user123",
    "author_id": "agent_789_user123",
    "author_type": "API",
    "message": "Hello, how can you help me today?",
    "created_at": "2024-01-01T12:00:01Z"
  },
  {
    "id": "msg_agent_001",
    "agent_id": "agent_789",
    "chat_id": "chat_123456",
    "user_id": "agent_789_user123",
    "author_id": "agent_789",
    "author_type": "AGENT",
    "message": "Hello! I'm an AI assistant. I can help you with various tasks...",
    "created_at": "2024-01-01T12:00:02Z"
  }
]
```

### 3. List Messages

```bash
curl -X GET "http://localhost:8000/v1/chats/chat_123456/messages" \
  -H "Authorization: Bearer <your_agent_token>"
```

**Response:**
```json
{
  "data": [
    {
      "id": "msg_agent_001",
      "agent_id": "agent_789",
      "chat_id": "chat_123456",
      "message": "Hello! I'm an AI assistant. I can help you with various tasks...",
      "author_type": "AGENT",
      "created_at": "2024-01-01T12:00:02Z"
    },
    {
      "id": "msg_user_001",
      "agent_id": "agent_789",
      "chat_id": "chat_123456",
      "message": "Hello, how can you help me today?",
      "author_type": "API",
      "created_at": "2024-01-01T12:00:01Z"
    }
  ],
  "has_more": false,
  "next_cursor": null
}
```

## Advanced Features

### Streaming Responses
Set `stream: true` in the message request to receive streaming responses:

```json
{
  "message": "Tell me a story",
  "stream": true
}
```

### Attachments
Include links, images, or files in messages:

```json
{
  "message": "Convert the image to Cyberpunk style",
  "attachments": [
    {
      "type": "image",
      "url": "https://your.image.url"
    }
  ]
}
```

### Search and Super Mode
Enable enhanced capabilities:

```json
{
  "message": "Find the latest news about AI",
  "search_mode": true,
  "super_mode": false
}
```

## Error Handling

The API returns standard HTTP status codes:
- `200`: Success
- `201`: Created
- `204`: No Content
- `400`: Bad Request
- `401`: Unauthorized
- `404`: Not Found
- `500`: Internal Server Error

Example error response:
```json
{
  "detail": "Chat not found"
}
```

## OpenAI Compatible API

IntentKit also provides an OpenAI-compatible API endpoint that allows you to use your agent with any OpenAI-compatible client or SDK. This is particularly useful for integrating with existing applications that already use the OpenAI API format.

For detailed, see the [OpenAI Compatible API Documentation](openai_compatible.md).

## API Reference

For complete API documentation with interactive examples, visit:
**https://open.service.crestal.network/v1/redoc**

If you are using LLM to generate code, providing it with this raw OpenAPI specification link is sufficient:
```
https://open.service.crestal.network/v1/openapi.json
```