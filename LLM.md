## Rules
- Do NOT add "Generated with Claude Code", "Co-Authored-By: Claude", or any AI-attribution footer to PR descriptions, commit messages, or code comments.
- Do NOT use the /commit or /pr slash commands. Use git and gh CLI directly.

# Novita AI Model Catalog

Use ONLY these model IDs. Do NOT invent or guess model IDs.

## API Endpoints

Novita AI supports two API-compatible endpoints. Choose based on which SDK the target repo uses:

| SDK / Interface | Base URL | Env Var |
|----------------|----------|---------|
| **OpenAI-compatible** | `https://api.novita.ai/openai` | `OPENAI_BASE_URL` or `OPENAI_API_BASE` |
| **Anthropic-compatible** | `https://api.novita.ai/anthropic` | `ANTHROPIC_BASE_URL` |

- API key for both: `NOVITA_API_KEY` (or follow the repo's existing env var pattern).
- If the repo uses the **OpenAI SDK** (`openai`, `langchain`, etc.) → use the OpenAI endpoint.
- If the repo uses the **Anthropic SDK** (`anthropic`, `@anthropic-ai/sdk`, etc.) → use the Anthropic endpoint.
- If the repo supports **both**, add both endpoints.

## Chat / Completion Models

| Model ID | Context | Max Output | Architecture | Features | Pricing (per M tokens) |
|----------|---------|------------|--------------|----------|----------------------|
| `moonshotai/kimi-k2.5` **(default)** | 262,144 | 262,144 | MoE | function_calling, structured_output, reasoning, vision | In: $0.6 / Out: $3 / Cache: $0.1 |
| `zai-org/glm-5` | 202,800 | 131,072 | MoE | function_calling, structured_output, reasoning | In: $1 / Out: $3.2 / Cache: $0.2 |
| `minimax/minimax-m2.5` | 204,800 | 131,100 | MoE | function_calling, structured_output, reasoning | In: $0.3 / Out: $1.2 / Cache: $0.03 |

## Embedding Models

| Model ID | Dimensions | Max Input | Pricing |
|----------|-----------|-----------|---------|
| `qwen/qwen3-embedding-0.6b` | 1024 | 8,192 | $0.014 / M tokens |

## Selection Rules

- If only one model slot: use `moonshotai/kimi-k2.5`
- If multiple model slots: default `moonshotai/kimi-k2.5`, also add `zai-org/glm-5` and `minimax/minimax-m2.5`
- If embedding slot: use `qwen/qwen3-embedding-0.6b`
- If vision/multimodal slot: use `moonshotai/kimi-k2.5` (supports image + video input)
