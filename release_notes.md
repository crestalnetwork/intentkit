## Model Catalog Refresh

- **GPT-5.6 price cuts passed through.** OpenAI reduced Terra by 20% and Luna by 80%; on OpenRouter both tiers currently run at half of OpenAI's list price, and the catalog now reflects each channel's real rate. Cached input stays at 10% of the input price everywhere.
- **DeepSeek V4 Flash official build.** Agents on DeepSeek V4 Flash now get the official release build, which posts large gains on agent and coding benchmarks. Existing agents move over automatically — no changes needed. Its maximum response length also grew twelvefold.
- **Qwen Flash upgraded to 3.7.** The new generation understands images and video, costs roughly a tenth of the previous flash on input, and existing agents are migrated automatically.
- **Across-the-board price corrections.** Every OpenRouter model's price is now sourced from the first-party endpoint we actually route to, rather than marketplace-wide averages. Several models became cheaper (Qwen Max, MiniMax M3, both MiMo tiers, Grok cache reads), one had been undercharged and was corrected (GLM 5.2), and DeepSeek cache-hit pricing is now consistent across channels.
- Fixed a routing configuration that could prevent Kimi K3 requests from reaching Moonshot's servers.

## Team Lead

- The built-in team lead orchestrator now runs on DeepSeek's new V4 Flash build, which leads agent-orchestration benchmarks while costing a fraction of the previous default model.

## Platform

- Connections to remote MCP tool servers were upgraded to the latest protocol SDK, and the service now properly identifies itself to those servers.
- On startup, the service now waits for its database, cache, and storage to be reachable before accepting work, making deploys and restarts more predictable.
- Routine AI SDK upgrades across the model integrations.
