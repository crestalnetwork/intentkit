# Testing Guide

## Test Types & Markers
- **Unit Tests**: Located in `tests/` (except `tests/bdd/`). Run in CI.
- **BDD Tests**: Located in `tests/bdd/`. Local only, loads `.env` via `tests/bdd/conftest.py`.

## BDD Database Isolation
- BDD tests use a separate `bdd` database (overrides `DB_NAME` from `.env`).
- `tests/bdd/conftest.py` drops and recreates `bdd` database before each test session.
- Requires PostgreSQL running with access to create/drop databases.

## Commands
```bash
pytest -m "not bdd"  # Unit tests only (CI)
pytest -m bdd        # BDD tests only (local)
pytest               # All tests
```

## Writing BDD Tests
Place in `tests/bdd/`. Mark with `@pytest.mark.bdd`. Access env vars from `.env`.
