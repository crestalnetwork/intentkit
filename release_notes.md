# Release v2.38.0

## Video Generation

The video toolset is now three models instead of six, and every one of them runs through OpenRouter:

- **Seedance 2.0 Mini** — the fast, inexpensive option, for drafts and quick iteration.
- **Seedance 2.5** — best for long-form storytelling and generating from a reference image.
- **MiniMax H3** — omni-modal generation with native audio, up to 2K.

**Sora, Sora Pro, Veo, Veo Fast and Grok video have been retired.** Agents that had any of these enabled will simply no longer show them; nothing else in the agent's setup changes, and MiniMax Hailuo keeps working under its existing entry, now on the newer H3 model. OpenAI is shutting its video API down entirely in September with no replacement, so Sora would have stopped working regardless.

**Video is now billed on what it actually costs.** Previously each video tool charged a fixed price per call, which meant short clips subsidised long ones. Charges now follow the real cost of the generation — model, resolution and length — so a quick draft costs a fraction of a long high-resolution render.

All three models are also available for image-to-video: supply a starting image and the model animates from it.

## Improvements

- Refreshed the platform's upstream dependencies, picking up upstream fixes across the model and payment integrations.
- Improved how failures from model providers are recognised, so temporary provider problems are retried and permanent ones surface promptly instead of being retried in vain.
- Fixed an issue where a starting image supplied in a format other than PNG could be misread by the provider.
- Fixed bugs in the video generation and agent payment modules.
