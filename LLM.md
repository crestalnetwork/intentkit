# LLM Integration Guide for IntentKit

This guide provides comprehensive information for Large Language Models (LLMs) working with the IntentKit autonomous agent framework.

## Project Overview

IntentKit is an autonomous agent framework that enables creation and management of AI agents with capabilities including:
- Blockchain interaction (EVM chains)
- Social media management (Twitter, Telegram)
- Extensible skill system
- Multi-agent support
- Custom skill integration

## Architecture Understanding

### Core Components

1. **Agent System** (`intentkit/core/`)
   - Agents are autonomous entities with configurable personalities and capabilities
   - Each agent has purpose, personality, principles, and custom prompts
   - Agents maintain memory and conversation history
   - Cost tracking and credit management per agent

2. **Skills System** (`intentkit/skills/`)
   - Modular capabilities that agents can use
   - Base class: `IntentKitSkill` extends LangChain's `BaseTool`
   - Skills have states: disabled, public, private
   - Available skills include: blockchain (CDP), social media (Twitter), search, image processing, etc.

3. **Entrypoints** (`app/entrypoints/`)
   - Multiple interfaces: web, Twitter, Telegram, API
   - OpenAI-compatible API endpoint available
   - Autonomous operation support

4. **Models and Storage**
   - PostgreSQL for persistent data
   - Redis for caching and session management
   - Agent configurations, credentials, memory, and skill states

## Working with Agents

### Agent Configuration Structure

```yaml
# Agent configuration fields
purpose: "Primary objective of the agent"
personality: "Character traits and behavior patterns"
principles: "Core rules and ethical guidelines"
prompt: "Main system prompt"
prompt_append: "Critical rules emphasized at the end"
```

### Prompt Composition

The system composes prompts as:
1. **System**: Combined `purpose` + `personality` + `principles` + `prompt`
2. **Conversation History**: User/Assistant alternating messages
3. **Current User Input**
4. **System Append**: `prompt_append` (optional, high priority rules)

### Best Practices for Prompt Engineering

1. **Purpose**: Clear, specific objective
2. **Personality**: Consistent character traits
3. **Principles**: Non-negotiable rules and boundaries
4. **Prompt**: Detailed instructions and context
5. **Prompt Append**: Critical rules repeated for emphasis

## Skills Development

### Skill Structure

```python
class CustomSkill(IntentKitSkill):
    name: str = "skill_name"
    description: str = "What this skill does"
    
    def _run(self, **kwargs) -> str:
        # Implementation
        pass
```

### Skill Configuration

```python
class SkillConfig(TypedDict):
    enabled: bool
    states: Dict[str, SkillState]  # disabled, public, private
    api_key_provider: str  # optional
```

### Available Skill Categories

- **Blockchain**: CDP (Coinbase Developer Platform), wallet management
- **Social Media**: Twitter, Telegram integration
- **Data**: DeFiLlama, Dune Analytics, CryptoCompare
- **Search**: Tavily, web scraping
- **Media**: Image processing, audio generation
- **Development**: GitHub integration
- **System**: Common utilities

## API Integration

### Entrypoints

1. **Web API** (`app/entrypoints/web.py`)
2. **OpenAI Compatible** (`app/entrypoints/openai_compatible.py`)
3. **Social Media**: Twitter, Telegram
4. **Autonomous**: Self-directed operation

### Authentication & Security

- API key management per skill
- User-specific configurations
- Rate limiting and cost controls
- Secure credential storage

## Development Workflow

### Setup

```bash
# Install dependencies
uv sync

# Environment configuration
cp example.env .env
# Edit .env with your API keys

# Database setup
# Configure PostgreSQL and Redis
```

### Agent Management

```bash
# Create agent
cd scripts
sh create.sh agent_name

# Export configuration
sh export.sh agent_name

# Edit agent_name.yaml

# Import updated configuration
sh import.sh agent_name
```

### Testing

- **Local API**: http://localhost:8000/redoc
- **Direct API calls**: OpenAI-compatible endpoints

## Error Handling

### Common Issues

1. **Rate Limiting**: `RateLimitExceeded` exception
2. **Validation Errors**: Pydantic validation failures
3. **Tool Errors**: Skill execution failures
4. **Credit Exhaustion**: Insufficient credits for operations

### Error Recovery

- Graceful degradation when skills fail
- Retry mechanisms for transient failures
- User-friendly error messages
- Logging and monitoring

## Performance Considerations

### Cost Management

- Token usage tracking per agent
- Credit-based billing system
- Cost metrics: avg, min, max, percentile-based
- Model selection based on cost/performance trade-offs

### Optimization

- Efficient prompt design
- Skill state management
- Memory optimization
- Caching strategies

## Security Guidelines

1. **API Key Management**: Secure storage, rotation
2. **Input Validation**: Sanitize all user inputs
3. **Rate Limiting**: Prevent abuse
4. **Access Control**: User-specific permissions
5. **Audit Logging**: Track all operations

## Monitoring and Debugging

### Logging

- Structured logging throughout the system
- Agent-specific log contexts
- Skill execution tracking
- Error reporting and alerting

### Metrics

- Token usage and costs
- Response times
- Success/failure rates
- User engagement metrics

## Contributing

### Adding New Skills

1. Extend `IntentKitSkill` base class
2. Implement required methods
3. Add configuration schema
4. Write tests
5. Update documentation

### Code Standards

- Follow existing patterns
- Use type hints
- Write comprehensive tests
- Document public APIs
- Follow security best practices

## Resources

- **Documentation**: `docs/` directory
- **API Reference**: http://localhost:8000/redoc
- **Examples**: `scripts/` directory
- **Skills Reference**: `intentkit/skills/`
- **Architecture**: `docs/architecture.md`

## Migration Notes

- **Package Manager**: Migrated from Poetry to uv
- **Environment Setup**: Delete `.venv` and run `uv sync`
- **Compatibility**: Maintain backward compatibility for existing agents

This guide should help LLMs understand the IntentKit framework structure, integration points, and best practices for working with autonomous agents and skills.