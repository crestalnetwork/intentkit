# Release v2.26.2

## Improvements

- Significantly cheaper scheduled tasks: fixed an issue in the autonomous task module where each step of a run was billed as if the whole conversation were new, instead of reusing the AI provider's prompt cache. Long multi-step runs now cost a fraction of what they did, with no change in behavior.
