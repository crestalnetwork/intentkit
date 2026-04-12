# Release v0.17.32

## Bug Fixes

- Gemini image and Veo video skills now respect Vertex AI configuration (`GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_PROJECT`), fixing failures when using Vertex AI credentials instead of a direct API key.
- LLM tool selector middleware now uses a dedicated model picker (`pick_tool_selector_model`) restricted to OpenAI, avoiding structured-output incompatibilities with Gemini and GLM that caused tool selection to fail silently or return descriptions instead of tool names (see langchain-ai/langchain#33651).
- Tool selector activation threshold raised from 10 to 15 tools, reducing unnecessary overhead for agents with moderate tool counts.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.17.31...v0.17.32
