.PHONY: mcp lint format

mcp:
	uv run scripts/sync_mcp_schemas.py

lint:
	uv run ruff format && uv run ruff check --fix
