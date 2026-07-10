# Release v2.15.0

## New Features

- **Latest AI models**: the model catalog now offers the newest generation across providers — OpenAI GPT-5.6 (Sol, Terra, and Luna tiers), xAI Grok 4.5, Claude Sonnet 5, Qwen3.7 Plus, and GLM 5.2 — with up-to-date pricing and capability data.
- **Seamless model upgrades**: retired models are now automatically routed to their successors. Existing agents configured with an older model keep working without any reconfiguration and transparently benefit from the newer model.
- **Official model providers**: requests routed through OpenRouter are now pinned to each model's first-party provider, ensuring consistent quality and behavior.

## Improvements

- Each model series now keeps a single, current version in the catalog, making model selection simpler.
- Agents created from the built-in templates and public agent gallery now use the latest models.
- Fixed inaccurate pricing data and unavailable model identifiers in the model catalog module.
