# LLMs

## Supported Models

IntentKit supports a wide range of LLM providers and models to give you flexibility in choosing the right model for your needs.

### Supported Providers

#### OpenAI
- **gpt-4o** - GPT-4o with vision and tool calling support
- **gpt-4o-mini** - Faster, more cost-effective version of GPT-4o
- **gpt-4.1-nano** - Ultra-fast and cost-effective model
- **gpt-4.1-mini** - Balanced performance and cost
- **gpt-4.1** - Latest GPT-4.1 with enhanced capabilities
- **o4-mini** - OpenAI's reasoning model with advanced problem-solving

#### DeepSeek
- **deepseek-chat** - DeepSeek V3 (0324) for general conversations
- **deepseek-reasoner** - DeepSeek R1 with enhanced reasoning capabilities

#### XAI (Grok)
- **grok-2** - Grok 2 model with tool calling support
- **grok-3** - Latest Grok 3 with search capabilities
- **grok-3-mini** - Compact version with reasoning capabilities

#### Eternal AI
- **eternalai** - Eternal AI (Llama-3.3-70B) for cost-effective inference

#### Reigent
- **reigent** - REI Network model for specialized tasks

#### Venice AI
- **venice-uncensored** - Venice Uncensored model
- **venice-llama-4-maverick-17b** - Venice Llama-4 Maverick 17B

### Model Capabilities

Each model supports different capabilities:

- **Tool/Skill Calls**: All models support function calling for skills
- **Structured Output**: JSON and structured response generation
- **Image Input**: Available on select OpenAI models (gpt-4o, gpt-4.1)
- **Reasoning**: Enhanced reasoning on o4-mini, deepseek-reasoner, and grok-3-mini
- **Search**: Native search functionality on gpt-4o, gpt-4o-mini, gpt-4.1-mini, gpt-4.1, and grok-3
- **Temperature Control**: Fine-tuning response creativity (not available on reasoning models)

### Pricing

Models are priced per million tokens with different rates for input and output tokens. The system automatically calculates costs based on token usage and converts to credits based on the current USDC exchange rate.

### Configuration

To use these models, configure the appropriate API keys in your environment:
- `OPENAI_API_KEY` for OpenAI models
- `DEEPSEEK_API_KEY` for DeepSeek models
- `XAI_API_KEY` for XAI/Grok models
- `ETERNAL_API_KEY` for Eternal AI models
- `REIGENT_API_KEY` for Reigent models
- `VENICE_API_KEY` for Venice AI models

The system will automatically route requests to the appropriate provider based on the model selected.
