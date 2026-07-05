.PHONY: mcp lint format

mcp:
	uv run scripts/scaffold_mcp_tools.py

lint:
	uv run ruff format && uv run ruff check --fix
