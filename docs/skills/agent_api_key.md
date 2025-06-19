# Agent API Key

IntentKit provides system skills for managing agent API keys that enable OpenAI-compatible API access to your agents. These skills allow you to retrieve existing API keys or generate new ones for programmatic access to your agent's capabilities.

## Available Skills

The following agent API key management skills are available:

- **Read Agent API Key** (`read_agent_api_key`): Retrieve the existing API key for the agent, or generate a new one if none exists
- **Regenerate Agent API Key** (`regenerate_agent_api_key`): Generate a new API key for the agent, revoking any existing key

## How to Use the API Key

Once you have obtained an API key using either of the above skills, you can use it to interact with your agent through the OpenAI-compatible API endpoint.

### API Endpoint

The API endpoint follows the OpenAI Chat Completions format:

```
POST {base_url}/v1/chat/completions
```

Where `{base_url}` is the base URL provided by the skill output.

### Authentication

The API key should be included in the `Authorization` header as a Bearer token:

```
Authorization: Bearer {your_api_key}
```

## Usage Examples

### cURL Example

Here's how to make a request using cURL:

```bash
curl -X POST "{base_url}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {your_api_key}" \
  -d '{
    "model": "agent",
    "messages": [
      {
        "role": "user",
        "content": "Hello, how can you help me today?"
      }
    ]
  }'
```

### OpenAI Python SDK Example

You can use the official OpenAI Python SDK by configuring it to use your IntentKit agent's endpoint:

```python
from openai import OpenAI

# Initialize the client with your agent's API key and base URL
client = OpenAI(
    api_key="{your_api_key}",
    base_url="{base_url}/v1"
)

# Make a chat completion request
response = client.chat.completions.create(
    model="agent",  # Model name is required but can be any value
    messages=[
        {
            "role": "user",
            "content": "Hello, how can you help me today?"
        }
    ]
)

print(response.choices[0].message.content)
```

### Using in Cherry Studio

Cherry Studio is a desktop client that supports OpenAI-compatible APIs. To use your IntentKit agent in Cherry Studio:

1. **Open Cherry Studio** and go to Settings

2. **Add a new API provider** with the following configuration:
   - **Provider Name**: IntentKit Agent (or any name you prefer)
   - **API Host**: Use the `base_url` provided by the skill output
   - **API Key**: Use the `api_key` provided by the skill output
   - **Model**: You can use any model name (e.g., "agent")

3. **Save the configuration** and select your IntentKit Agent as the active provider

4. **Start chatting** with your agent through Cherry Studio's interface

## API Compatibility

The IntentKit agent API is compatible with the OpenAI Chat Completions API format, supporting:

- **Standard chat messages** with role and content
- **Image attachments** (when supported by the agent)
- **Streaming responses** using Server-Sent Events
- **All other parameters** is valid but will be ignored

## Important Notes

- **Single Message Processing**: The API currently processes only the last message from the messages array, memory is managed by the agent in cloud
- **Authentication Required**: All requests must include a valid API key in the Authorization header
- **Agent-Specific**: Each API key is tied to a specific agent and can only access that agent's capabilities
- **Key Security**: Keep your API keys secure and regenerate them if compromised
