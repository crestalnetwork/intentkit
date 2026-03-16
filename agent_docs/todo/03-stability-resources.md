# Priority 3: Stability & Resource Management

These issues can cause memory leaks, connection exhaustion, or service instability under load.

---

## 3.1 Executor Cache: No Lock + No Eviction

**Location:** `intentkit/core/executor.py:34-38, 252-281`
**Issue:** (a) Global dicts `_agents`/`_agents_updated` read/written without asyncio.Lock — concurrent requests can double-build the same executor. (b) No eviction mechanism — cache grows indefinitely, eventually OOM. Manager cache (`manager/engine.py:38-42`) has the same lock issue but does have TTL cleanup.
**Fix:** Add `asyncio.Lock` per agent_id (or global with quick check-and-set). Add LRU/TTL eviction.

> **User notes:**

---

## 3.2 Twitter Client Cache Unbounded Growth

**Location:** `intentkit/clients/twitter.py:20-21`
**Issue:** `_clients_linked` and `_clients_self_key` module-level dicts grow indefinitely. Each entry holds `AgentData` + `AsyncClient`. No eviction, TTL, or max-size.
**Fix:** Add LRU/TTL eviction mechanism.

> **User notes:**

---

## 3.3 HTTP Clients Missing Timeouts

**Location:** `clients/twitter.py:378,411` (image download/upload), `clients/s3.py:112` (store_image), `utils/ens.py:85` (Web3 RPC)
**Issue:** `httpx.AsyncClient()` and `Web3.HTTPProvider()` created with no timeout. Slow/unresponsive servers block the async event loop indefinitely.
**Fix:** Add explicit timeout to all external HTTP clients (e.g., `httpx.AsyncClient(timeout=30)`).

> **User notes:**

---

## 3.4 Twitter Media Upload File Handle Leak

**Location:** `intentkit/clients/twitter.py:401-406`
**Issue:** `open(tmp_file_path, "rb")` passed into `files` dict but never explicitly closed. If upload fails before httpx closes it, file descriptor leaks. The `finally` block removes the file but doesn't close the handle.
**Fix:** Use `with open(...) as f:` or store the file object and close in `finally`.

> **User notes:**

---

## 3.5 Supabase Skills: New Client Every Invocation

**Location:** `intentkit/skills/supabase/fetch_data.py:62`, `insert_data.py:55`, `delete_data.py:55`, `invoke_function.py:50`, `update_data.py`, `upsert_data.py`
**Issue:** Every invocation calls `create_client()` creating a new Supabase client. Connection pools never reused or closed. Under load, exhausts file descriptors.
**Fix:** Cache and reuse clients per agent/config, similar to Twitter client pattern (but with eviction).

> **User notes:**

---

## 3.6 Dual Connection Pool to Same Database

**Location:** `intentkit/config/db.py:31-114`
**Issue:** `init_db` creates both psycopg `AsyncConnectionPool` (3 min, 6 max) and SQLAlchemy `create_async_engine` (3 + 6 overflow). Up to 15 connections to the same DB.
**Fix:** Consolidate into a single connection pool.

> **User notes:**

---

## 3.7 Alert Handler: Unbounded Queue + Non-Atomic Rate Limit

**Location:** `intentkit/utils/alert_handler.py:113, 117-148`
**Issue:** (a) `Queue()` has no `maxsize` — if background worker blocks, queue grows to OOM. (b) Rate limit check (zcard) and add (zadd) are not in the same pipeline — TOCTOU race allows exceeding the limit.
**Fix:** Add `maxsize` to Queue. Use Redis pipeline or Lua script for atomic rate check+add.

> **User notes:**

---

## 3.8 `raw_chunks` Unbounded Memory Growth

**Location:** `intentkit/core/engine.py:760, 926`
**Issue:** Every stream chunk appended to `raw_chunks` list. In `super_mode` with high recursion limits, this can be very large. On empty response, entire list is logged at ERROR level (huge log entry).
**Fix:** Cap list size (e.g., keep last N chunks), or only collect when debugging.

> **User notes:**

---

## 3.9 No Response Size Limit on HTTP Downloads

**Location:** `clients/s3.py:113` (store_image), `clients/twitter.py:379` (image download), `utils/opengraph.py:85` (HTML parse)
**Issue:** Full response body loaded into memory with no size check. Malicious/misconfigured URL could return gigabytes.
**Fix:** Add `max_content_length` check before reading full response.

> **User notes:**

---

## 3.10 Manager Cache Cleanup Only on Request

**Location:** `intentkit/core/manager/engine.py:234-241`
**Issue:** `_cleanup_cache` only runs inside `_get_manager_executor`. If no new manager requests come in, expired entries stay in memory forever.
**Fix:** Add periodic cleanup (e.g., via scheduler) or use a self-evicting cache structure.

> **User notes:**

---

## 3.11 OAuth2 Callback: Blocking Sync Calls in Async Endpoint

**Location:** `app/services/twitter/oauth2_callback.py:104, 115-121`
**Issue:** `oauth2_user_handler.get_token()` and `tweepy.Client.get_me()` are synchronous HTTP calls in an async endpoint, blocking the event loop. `oauth2_refresh.py:54` correctly uses `asyncio.to_thread`.
**Fix:** Wrap both calls with `await asyncio.to_thread(...)`.

> **User notes:**

---

## 3.12 Global Mutable State Without Synchronization

**Location:** `utils/telegram_alert.py:13-15`, `utils/slack_alert.py:14-17`, `utils/alert_handler.py:139`
**Issue:** Module-level globals (`_telegram_bot_token`, `_slack_client`, `_dropped_count`) mutated without locks. Concurrent access could cause races.
**Fix:** Add locks or use thread-safe patterns.

> **User notes:**
