# Priority 5: Low Priority Improvements

Minor issues, polish items, and nice-to-haves.

---

## 5.1 `CALL_AGENT_TIMEOUT=300` Comment Says "3 minutes" (Actually 5)

**Location:** `intentkit/core/system_skills/call_agent.py:15`
**Fix:** Correct comment to "5 minutes", or change timeout to 180 if 3 min was intended.

> **User notes:**

---

## 5.2 Web Search Hardcoded Cost `amount += 35`

**Location:** `intentkit/core/engine.py:386`
**Issue:** Magic number with no constant name or config.
**Fix:** Extract to a named constant.

> **User notes:**

---

## 5.3 Local `get_agent` Shadows Module-Level Import

**Location:** `intentkit/core/engine.py:731` (shadows import at line 41)
**Fix:** Rename the local closure to `get_agent_for_context` or similar.

> **User notes:**

---

## 5.4 `random` Instead of `secrets` for Transaction References

**Location:** `intentkit/utils/random.py:16`
**Issue:** Uses `random.choice()` which is not cryptographically secure. If references need to be unpredictable, this is a problem.
**Fix:** Use `secrets.choice()` if unpredictability matters.

> **User notes:**

---

## 5.5 OAuth2 PKCE Codes Stored in Redis Without TTL

**Location:** `intentkit/clients/twitter.py:512-513`
**Issue:** PKCE verifier/challenge stored without expiration. Should be single-use and short-lived.
**Fix:** Add `ex=300` (5 min TTL) to the `kv.set()` calls.

> **User notes:**

---

## 5.6 Duplicate `NetworkId` Enum Value (56)

**Location:** `intentkit/utils/chain.py:123, 136`
**Issue:** `BinanceMainnet = 56` and `BnbMainnet = 56` are aliases. `NetworkId(56)` always returns `BinanceMainnet`.
**Fix:** Remove one alias or document the intentional aliasing.

> **User notes:**

---

## 5.7 Go Integration: No HTTP Client Timeout

**Location:** `integrations/telegram/api/client.go:15-19`
**Fix:** Add `client.SetTimeout(30 * time.Second)`.

> **User notes:**

---

## 5.8 Go Integration: DSN Hardcodes `sslmode=disable`

**Location:** `integrations/telegram/config/config.go:38`
**Fix:** Make `sslmode` configurable via environment variable.

> **User notes:**

---

## 5.9 Go Integration: No Bot Token Change Detection

**Location:** `integrations/telegram/bot/manager.go:105-113`
**Issue:** `ensureBotRunning` only checks if a bot exists, not if the token changed. Old bot runs with stale token.
**Fix:** Track token hash and restart bot on change.

> **User notes:**

---

## 5.10 Signal Handler Uses `sys.exit()` in Async Context

**Location:** `app/entrypoints/tg.py:117-124`, `app/entrypoints/discord.py:99-106`
**Issue:** Abruptly terminates without awaiting async resource cleanup.
**Fix:** Use `asyncio.get_event_loop().add_signal_handler()` with a shutdown event.

> **User notes:**

---

## 5.11 f-string Logging Throughout Project

**Issue:** Pervasive use of `logger.error(f"Error: {e}")` instead of `logger.error("Error: %s", e)`. Evaluates f-string even when log level inactive.
**Fix:** Low priority, address opportunistically during other changes.

> **User notes:**

---

## 5.12 Scheduler Duplicate Comment Lines

**Location:** `intentkit/core/scheduler.py:93-94, 145-146`
**Fix:** Remove duplicate lines.

> **User notes:**

---

## 5.13 Session Docstring Shows SQLAlchemy 1.x Pattern

**Location:** `intentkit/config/db.py:137`
**Issue:** Docstring shows `session.query(...)` which is legacy 1.x.
**Fix:** Update docstring to 2.0 style.

> **User notes:**

---

## 5.14 Missing `updated_at` on Append-Style Tables

**Location:** `ChatMessageTable`, `AgentActivityTable`, `AgentPostTable`, `CreditEventTable`, `CreditTransactionTable`
**Issue:** No `updated_at` column. Acceptable for truly append-only tables, but worth confirming intent.
**Fix:** Add `updated_at` where records can be modified, skip for append-only.

> **User notes:**

---

## 5.15 Twitter `search_tweets` Timezone-Naive Datetime

**Location:** `intentkit/skills/twitter/search_tweets.py:55-56`
**Issue:** Uses `datetime.datetime.now()` (naive) while `post_tweet.py` correctly uses `datetime.now(tz=UTC)`.
**Fix:** Use timezone-aware datetime consistently.

> **User notes:**

---

## 5.16 Tavily Search Duplicates API Key Logic

**Location:** `intentkit/skills/tavily/tavily_search.py:86-93` vs `base.py:10-22`
**Issue:** `_arun()` re-implements key resolution instead of using `self.get_api_key()`.
**Fix:** Use the base class method.

> **User notes:**

---

## 5.17 Generic `Exception` Raised Instead of Specific Types

**Location:** `clients/twitter.py:164-193`, `utils/chain.py:342,351,374`
**Issue:** Bare `raise Exception(...)` instead of `ValueError`, `AgentError`, or custom types.
**Fix:** Use specific exception types for better caller handling.

> **User notes:**

---

## 5.18 `Decimal("0")` vs `0.0` Inconsistency in Credit System

**Location:** `intentkit/models/credit/account.py:672-687`
**Issue:** Float literals `0.0` passed where `Decimal` columns expected.
**Fix:** Use `Decimal("0")` for consistency.

> **User notes:**

---

## 5.19 `get_session()` Docstring Shows Legacy Pattern

**Location:** `intentkit/config/db.py:137`
**Issue:** Already covered in 5.13, merged.

> **User notes:**

---

## 5.20 Redundant Tool Deduplication

**Location:** `intentkit/core/executor.py:143-154` + `middleware.py:161-166`
**Issue:** Tools deduplicated at build time, then again on every model call.
**Fix:** Remove the redundant deduplication in middleware if build-time dedup is reliable.

> **User notes:**
