# Configuration

## IntentKit configuration

The application can be configured using environment variables or AWS Secrets Manager. Key configuration options:

- `ENV`: Environment (local or others)
- `DB_*`: PostgreSQL Database configuration (Required)
- `OPENAI_API_KEY`: OpenAI API key for agent interactions (Required)
- `CDP_*`: Coinbase Developer Platform configuration (Optional)

See [example.env](../example.env) for all available options.
