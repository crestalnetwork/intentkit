#!/bin/bash
set -e

echo "Running code formatters and linters..."

# Check if running in CI mode (no fixes)
if [ "$1" = "ci" ]; then
    echo "Running in CI mode - checking only, not fixing..."
    uv run ruff format --check
    uv run ruff check
else
    uv run ruff format
    uv run ruff check --fix
fi

echo "Running type checker..."
# Pre-existing diagnostics are frozen in .basedpyright/baseline.json;
# only new issues fail. After fixing baselined ones, the baseline
# auto-shrinks; regenerate intentionally with: basedpyright --writebaseline
uv run basedpyright

echo "Checking architecture layer contract..."
# Layer order is defined in [tool.importlinter] in pyproject.toml
uv run lint-imports

echo "Checking dependency declarations..."
uv run deptry .
