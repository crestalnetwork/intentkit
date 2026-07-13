# Release v2.21.0

## New Features

- **Smarter conversation memory**: long conversations are now compressed with a new in-house strategy that adapts to how active the chat is. Active conversations keep as much context as possible (and stay prompt-cache friendly); a chat resumed after hours or days is compacted more aggressively, cutting input cost and speeding up the first reply.
- **Compression that keeps what matters**: instead of blindly trimming old messages, the agent now preserves the conversation's opening exchange and the most recent round in full, and replaces everything in between with an AI-written summary — so the agent still remembers how the conversation started and what was just said.
- **Per-model tuning**: the compression thresholds (for active, recent, and idle conversations) can now be adjusted per model in the model catalog, with sensible defaults derived from each model's context window.

## Improvements

- Extremely long histories are now summarized reliably in stages, even when they exceed the summarizer model's own capacity.
- A failed summarization no longer risks corrupting conversation history — the agent simply keeps the full history and retries later.
- Fixed issues in the history compression module that could cause repeated re-summarization of the same conversation.
