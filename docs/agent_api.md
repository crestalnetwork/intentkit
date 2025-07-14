# Agent API Documentation

This guide teaches LLMs how to interact with IntentKit agent APIs when building applications. The agent API provides endpoints to create chat threads, send messages, and retrieve conversation history.

## Base URL and Authentication

All API endpoints are prefixed with `/v1/` and require authentication using a Bearer token.

**Base URL:** `http://localhost:8000/v1/` when local development. For production, you will get it when you get the key.

**Authentication:** Include the agent token in the Authorization header:
```
Authorization: Bearer <your_agent_token>
```

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

## Core API Endpoints

### Thread Management

#### Create Chat Thread
- **Method:** `POST /chats`
- **Description:** Create a new chat thread
- **Parameters:**
  - `user_id` (query, optional): User identifier
- **Response:** Chat object with `id`, `agent_id`, `user_id`, `summary`, `rounds`

#### List Chat Threads
- **Method:** `GET /chats`
- **Description:** List all chat threads for the user
- **Parameters:**
  - `user_id` (query, optional): User identifier
- **Response:** Array of Chat objects

#### Get Chat Thread
- **Method:** `GET /chats/{chat_id}`
- **Description:** Get a specific chat thread
- **Response:** Chat object

#### Update Chat Thread
- **Method:** `PATCH /chats/{chat_id}`
- **Description:** Update chat thread (currently only summary)
- **Body:** `{"summary": "Updated summary"}`

#### Delete Chat Thread
- **Method:** `DELETE /chats/{chat_id}`
- **Description:** Delete a chat thread
- **Response:** 204 No Content

### Message Management

#### Send Message
- **Method:** `POST /chats/{chat_id}/messages`
- **Description:** Send a message to a chat thread
- **Body:**
  ```json
  {
    "message": "Your message here",
    "user_id": "user123",
    "stream": false,
    "search_mode": false,
    "super_mode": false,
    "attachments": [
      {
        "type": "link",
        "url": "https://example.com"
      }
    ]
  }
  ```
- **Response:** Array of ChatMessage objects (user message + agent responses)

#### List Messages
- **Method:** `GET /chats/{chat_id}/messages`
- **Description:** Get message history with pagination
- **Parameters:**
  - `cursor` (query, optional): Pagination cursor (message ID)
  - `limit` (query, optional): Number of messages (1-100, default: 20)
- **Response:** `ChatMessagesResponse` with `data`, `has_more`, `next_cursor`

#### Retry Message
- **Method:** `POST /chats/{chat_id}/messages/retry`
- **Description:** Retry the last message in a chat thread
- **Response:** Array of ChatMessage objects

#### Get Message
- **Method:** `GET /messages/{message_id}`
- **Description:** Get a specific message by ID
- **Response:** ChatMessage object

## Python Example

Here's a complete Python example using the `requests` library:

```python
import requests
import json

class AgentAPIClient:
    def __init__(self, base_url="http://localhost:8000/v1", token=None):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def create_chat(self, user_id=None):
        """Create a new chat thread."""
        params = {"user_id": user_id} if user_id else {}
        response = requests.post(
            f"{self.base_url}/chats",
            headers=self.headers,
            params=params
        )
        return response.json()
    
    def send_message(self, chat_id, message, user_id=None, stream=False):
        """Send a message to a chat thread."""
        data = {
            "message": message,
            "stream": stream
        }
        if user_id:
            data["user_id"] = user_id
            
        response = requests.post(
            f"{self.base_url}/chats/{chat_id}/messages",
            headers=self.headers,
            json=data
        )
        return response.json()
    
    def list_messages(self, chat_id, cursor=None, limit=20):
        """List messages in a chat thread."""
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
            
        response = requests.get(
            f"{self.base_url}/chats/{chat_id}/messages",
            headers=self.headers,
            params=params
        )
        return response.json()

# Usage example
client = AgentAPIClient(token="your_agent_token_here")

# Create a chat thread
chat = client.create_chat(user_id="user123")
chat_id = chat["id"]

# Send a message
messages = client.send_message(
    chat_id=chat_id,
    message="Hello, what can you help me with?",
    user_id="user123"
)

# List all messages
message_history = client.list_messages(chat_id=chat_id)
print(f"Found {len(message_history['data'])} messages")
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
  "message": "Analyze this website",
  "attachments": [
    {
      "type": "link",
      "url": "https://example.com"
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

## Best Practices

1. **Always handle errors:** Check HTTP status codes and parse error responses
2. **Use pagination:** For large message histories, use cursor-based pagination
3. **Store chat IDs:** Keep track of chat thread IDs for ongoing conversations
4. **Respect rate limits:** Implement appropriate delays between requests
5. **Use streaming for long responses:** Enable streaming for better user experience

## API Documentation

For complete API documentation with interactive examples, visit:
**http://localhost:8000/v1/redoc**

This provides a comprehensive OpenAPI specification with all endpoints, parameters, and response schemas. 