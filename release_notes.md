# Release v2.26.1

## Improvements

- More resilient replies: temporary AI provider hiccups — dropped connections, timeouts, rate limits, brief outages — are now retried automatically, including interruptions that happen midway through generating a response. When a request truly cannot be completed, the conversation now shows a proper error notice instead of occasionally recording the raw failure as if it were the agent's reply.
- Faster long conversations: removed an ineffective context-trimming layer that added overhead to every reply and reduced caching efficiency in long threads. Long-history management is now handled entirely by the tiered history compression.
