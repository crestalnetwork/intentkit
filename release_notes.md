# Release v2.27.2

## Improvements

- More reliable web-enabled agents: when a model's built-in web search or page-fetch briefly fails upstream, or a response is cut off in transit, the request is now retried automatically instead of surfacing as an error. Genuinely permanent failures — such as an exhausted usage limit — still stop right away, so real problems stay visible.
- Routine maintenance: refreshed the underlying software dependencies to their latest compatible versions.
