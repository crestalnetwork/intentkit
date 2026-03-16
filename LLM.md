# IntentKit LLM Guide

## Architecture

- `intentkit/` — pip package
  - `core/` — agent system (LangGraph)
    - `manager/` — single agent manager
    - `system_skills/` — built-in system skills
  - `models/` — Pydantic + SQLAlchemy dual models
  - `config/` — system config (DB, LLM keys, skill provider keys)
  - `skills/` — skill system (LangChain BaseTool)
  - `abstracts/` — interfaces for core/ and skills/
  - `utils/` — utilities
  - `clients/` — external service clients
- `app/` — API server, autonomous runner, background scheduler
- `frontend/` — Next.js agent management UI (see `frontend/AGENTS.md`)
- `integrations/` — platform integrations (each has its own `AGENTS.md`)
  - `telegram/` — Telegram bot integration
- `scripts/` — ops & migration scripts
- `tests/` — `tests/core/`, `tests/api/`, `tests/skills/`

## Tech Stack & Gotchas

- Package manager: **uv**. Activate venv: `source .venv/bin/activate`
- Lint: `ruff format & ruff check --fix` after edits
- Type check: **BasedPyright** — ensure no errors in changed files
- **SQLAlchemy 2.0** — do NOT use legacy 1.x API
- **Pydantic V2** — do NOT use V1 API
- Testing: **pytest**

## Rules

- English for code comments and search queries
- Do not git commit unless explicitly asked
- Import dependency order (left cannot import right): `utils → config → models → abstracts → clients → skills → core`
- **No ForeignKey constraints**: All tables intentionally omit `ForeignKey` constraints. Do NOT add FK constraints to any table definition.
- **AgentCore ↔ Template sync**: `AgentCore` (Pydantic) is the shared base for both `Agent` and `Template`. When adding/removing fields in `AgentCore`, you MUST also update `TemplateTable` (SQLAlchemy columns in `intentkit/models/template.py`) to match. The `Template` Pydantic model inherits from `AgentCore` automatically, but the DB schema does not. Agent-specific fields like `slug` belong in `AgentUserInput`, not `AgentCore`.

## Detailed Guides

- Skills: `agent_docs/skill_development.md`
- Git/PR/Release: `agent_docs/ops_guide.md`
- Testing: `agent_docs/test.md`
