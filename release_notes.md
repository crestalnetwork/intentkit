## Improvements

- Clearer diagnostics for model provider failures: when a model provider rejects or fails a request, error logs and alerts now include the provider's status code and response details, instead of only a generic message like "Provider returned error". This applies to agent runs and to background history summarization, and makes it possible to tell at a glance whether a failure was a provider outage or a rejected request.
