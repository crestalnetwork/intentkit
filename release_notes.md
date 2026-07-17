# Release v2.27.4

## Bug Fixes

- Fixed web-enabled agents on OpenRouter models stalling mid-task. Certain models would occasionally emit their internal tool-call instructions as visible text instead of actually running the tool, leaving the task unfinished. These agents now use our own web search and page-reading tools, which run reliably across every model, so multi-step research and publishing flows complete as expected.
