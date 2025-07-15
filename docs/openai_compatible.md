# OpenAI Compatible API

IntentKit provides system skills for managing agent API keys that enable OpenAI-compatible API access to your agents. The system supports two types of API keys with different access levels:

- **Private API Key (sk-)**: Can access all skills (public and owner-only)
- **Public API Key (pk-)**: Can only access public skills

## How to Use the API Keys

Once you have obtained API keys using either of the above skills, you can use them to interact with your agent through the OpenAI-compatible API endpoint. Choose the appropriate key based on your access requirements.

### API Endpoint

The API endpoint follows the OpenAI Chat Completions format:

```
POST {base_url}/v1/chat/completions
```

Where `{base_url}` is the base URL provided by the skill output.

### Authentication

The API key should be included in the `Authorization` header as a Bearer token. Use either your private (sk-) or public (pk-) key depending on your access needs:

```
Authorization: Bearer {your_api_key}
```

**Examples:**
- Private key: `Authorization: Bearer sk-1234567890abcdef...`
- Public key: `Authorization: Bearer pk-1234567890abcdef...`

## Usage Examples

### cURL Example

Here's how to make a request using cURL with either key type:

**Using Private Key (full access):**
```bash
curl -X POST "{base_url}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your_private_key_here" \
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

**Using Public Key (public skills only):**
```bash
curl -X POST "{base_url}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer pk-your_public_key_here" \
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
```

### OpenAI Python SDK Example

You can use the official OpenAI Python SDK by configuring it to use your IntentKit agent's endpoint:

**Using Private Key (full access):**
```python
from openai import OpenAI

# Initialize the client with your agent's private API key and base URL
client = OpenAI(
    api_key="sk-your_private_key_here",  # Private key for full access
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

**Using Public Key (public skills only):**
```python
from openai import OpenAI

# Initialize the client with your agent's public API key and base URL
client = OpenAI(
    api_key="pk-your_public_key_here",  # Public key for limited access
    base_url="{base_url}/v1"
)

# Make a chat completion request (only public skills available)
response = client.chat.completions.create(
    model="agent",
    messages=[
        {
            "role": "user",
            "content": "What public information can you provide?"
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
   - **API Key**: Use either the private (`sk-`) or public (`pk-`) API key depending on your needs
   - **Model**: You can use any model name (e.g., "agent")

   **Key Selection Guidelines:**
   - Use **private key (sk-)** for personal use or when you need access to all agent capabilities
   - Use **public key (pk-)** when sharing access or when you only need public skills

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
- **Access Control**: 
  - Private keys (sk-) provide full access to all agent skills
  - Public keys (pk-) are restricted to public skills only
  - Choose the appropriate key type based on your security requirements
- **Key Management**: Both key types are generated and managed together through the system skills
