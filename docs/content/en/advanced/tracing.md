# Tracing & Observability

IntentKit can send a full trace of every agent run to [Langfuse](https://langfuse.com), an external observability platform. A trace captures each step the agent took — the prompts sent to the model, the model's replies, every tool call and its result, token usage, latency and errors. It is the fastest way to understand *why* an agent behaved the way it did, to debug failures, and to monitor cost and performance in production.

Tracing is entirely optional — if Langfuse is not configured, agents run normally without it.

> **Note:** LangChain ships a built-in LangSmith tracer that activates on the `LANGSMITH_TRACING` / `LANGCHAIN_TRACING_V2` environment variables, independent of IntentKit. IntentKit no longer integrates with LangSmith, so leave those variables unset (or `false`) — otherwise LangChain will keep sending traces to LangSmith alongside Langfuse.

## Langfuse

[Langfuse](https://langfuse.com) is an open-source LLM observability platform. You can use their managed cloud or self-host it.

### Register

**Cloud:** sign up at [cloud.langfuse.com](https://cloud.langfuse.com), create a project, then open **Settings → API Keys** and create a key pair (a public key and a secret key).

**Self-hosted:** follow the [Langfuse self-hosting guide](https://langfuse.com/self-hosting). You get the same public/secret key pair from your own instance.

### Configure

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
# LANGFUSE_BASE_URL=https://cloud.langfuse.com   # optional, defaults to Langfuse Cloud
```

Langfuse is enabled as soon as **both** keys are present. Set `LANGFUSE_BASE_URL` to your own URL when self-hosting (the older name `LANGFUSE_HOST` is also accepted). Each conversation is grouped into a single session, so a whole chat appears as one session in the Langfuse UI.

## Where to set these

These values are loaded like every other IntentKit setting — from environment variables (for example a `.env` file or your deployment's environment) or from AWS Secrets Manager. Quotes around values are stripped automatically. See [Configuration](../configuration/) for the general configuration mechanism.

## Verifying

Start the API server, send a message to an agent, then open your Langfuse dashboard — the run should appear within a few seconds. On startup the logs also confirm when Langfuse is active (a line reading `Langfuse tracing enabled`).
