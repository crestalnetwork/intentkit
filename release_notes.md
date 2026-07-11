# Release v2.18.0

## New Features

- **One System Prompt**: the five separate prompt fields (Purpose, Personality, Principles, Knowledge Base, Advanced) are merged into a single "System Prompt" written in Markdown. It holds up to 200,000 characters and supports level-2+ headings, so you can structure the agent's role, personality, rules, and knowledge in one place, your way. Existing agents are migrated automatically — their old fields are stitched into the new prompt under matching section headings.
- **Description is a first-class field**: the short public description is now edited right in the agent form instead of only through the publish flow. It appears in agent listings and search, and it is what other agents read when they delegate work to this one as a sub-agent. Agents that never set a description automatically inherit their old Purpose text.
- **Team lead upgrades**: the lead's agent manager creates and updates agents with the new single system prompt and can set the description too, and its agent listings show the description consistently.

## Improvements

- All built-in public seed agents were converted to the new single-prompt format.
- Avatar generation now handles very large prompts gracefully.
- Internal cleanup of prompt assembly and validation logic.
