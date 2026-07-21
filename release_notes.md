# Release v2.30.0

## New Features

- Upgraded the Gemini model lineup: Gemini 3.6 Flash replaces Gemini 3.5 Flash as the default flash-tier model, and Gemini 3.5 Flash Lite replaces Gemini 3.1 Flash Lite as the lite-tier model. Both are available natively and via OpenRouter, and agents using the previous models switch over automatically — no configuration change needed.
- Pricing follows the new models: Gemini 3.6 Flash produces output about 17% cheaper than its predecessor, while Gemini 3.5 Flash Lite costs slightly more than the old lite model (still the budget tier). Public agent templates and built-in web search now run on Gemini 3.6 Flash.

## Improvements

- Streamlined the agent management UI: the agent creation and editing pages now share one consistent form, and unused frontend code was removed for a lighter build.
- Internal cleanup of legacy compatibility code, one-off migration scripts, and orphaned modules left over from earlier refactors.
