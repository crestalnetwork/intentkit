# Priority 6: Testing & CI/CD

Test coverage gaps and CI pipeline improvements.

---

## 6.1 No API Endpoint Tests

**Location:** `tests/api/` directory does not exist
**Issue:** CLAUDE.md mentions `tests/api/` but it doesn't exist. All API endpoints (`app/entrypoints/`) have zero test coverage.
**Fix:** Create API integration tests for critical endpoints (auth, chat, agent CRUD).

> **User notes:**

---

## 6.2 ~90% of Skills Untested

**Location:** `tests/skills/` — only 5 test files for 45+ skill directories
**Issue:** Tested: `create_post`, `pancakeswap`, `ui`, `update_memory`, `x402_safe_funding`. Untested: `cdp`, `erc20`, `erc721`, `twitter`, `slack`, `github`, `jupiter`, `lifi`, `morpho`, `superfluid`, `firecrawl`, `dune_analytics`, `enso`, `http`, and many more. These include DeFi skills that handle real funds.
**Fix:** Prioritize tests for financial skills (DeFi, credit) and security-critical skills (HTTP, Slack).

> **User notes:**

---

## 6.3 No Tests for System Skills, Manager, Middleware

**Location:** `intentkit/core/system_skills/`, `intentkit/core/manager/`, `intentkit/core/middleware.py`, `intentkit/core/account_checking.py`, `intentkit/core/statistics.py`
**Issue:** Core modules with zero dedicated test coverage.
**Fix:** Add tests for middleware (credit check, trim messages) and system skills (call_agent).

> **User notes:**

---

## 6.4 CI Release Pipeline Doesn't Run Tests

**Location:** `.github/workflows/build.yml`
**Issue:** Builds and publishes Docker images + PyPI packages on release without running tests. Tests only run in `lint.yml` on PRs.
**Fix:** Add test step before publish in the release workflow.

> **User notes:**

---

## 6.5 Lint Script Doesn't Run Type Checking

**Location:** `lint.sh`
**Issue:** Runs `ruff format` + `ruff check` + JSON schema validation, but not BasedPyright. CLAUDE.md says "ensure no errors in changed files" but CI doesn't enforce this.
**Fix:** Add BasedPyright to lint script and CI.

> **User notes:**

---

## 6.6 Dependabot Only Monitors pip

**Location:** `.github/dependabot.yml`
**Issue:** Missing: `github-actions` (for action version updates), `docker` (Dockerfile base images), `npm` (frontend Next.js app).
**Fix:** Add ecosystem entries for github-actions, docker, and npm.

> **User notes:**

---

## 6.7 Inconsistent GitHub Action Versions

**Location:** `.github/workflows/lint.yml` vs `build.yml`
**Issue:** `setup-python@v4` vs `v5`, `setup-uv@v5` vs `v4`.
**Fix:** Align to latest versions across all workflows.

> **User notes:**

---

## 6.8 .env.example Incomplete

**Issue:** Missing: `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD`, `REDIS_SSL`, `ETERNAL_API_KEY`, `REIGENT_API_KEY`, `VENICE_API_KEY`, `OLLAMA_BASE_URL`.
**Fix:** Add missing variables with comments.

> **User notes:**

---

## 6.9 BasedPyright Suppressions Reduce Type Checking Value

**Location:** `pyproject.toml:127-136`
**Issue:** 8 `report*` rules disabled, including `reportUnknownMemberType`, `reportUnknownVariableType`, `reportUnknownArgumentType`.
**Fix:** Gradually re-enable suppressions as type coverage improves.

> **User notes:**

---

## 6.10 Multiple TODO/FIXME Comments Unaddressed

**Location:** `skills/web_scraper/website_indexer.py:448`, `skills/web_scraper/scrape_and_index.py:156,256`, `skills/firecrawl/query.py:113`
**Issue:** Repeated "TODO: Fix config reference" across multiple files — systematic config reference problem.
**Fix:** Investigate and resolve the underlying config reference issue.

> **User notes:**
