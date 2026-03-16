# Priority 2: Data Integrity & Financial Correctness

These issues can cause data loss, incorrect billing, or corrupt financial records.

---

## 2.1 Exception Handler Destroys Entire Conversation History

**Location:** `intentkit/core/engine.py:905-917`
**Issue:** The catch-all `except Exception` in `stream_agent_raw` calls `clear_thread_memory`, deleting ALL checkpoint data for the thread. A transient network error or temporary LLM API failure wipes the user's entire conversation.
**Fix:** Only clear thread memory for known unrecoverable corruption states, not all exceptions.

> **User notes:**

---

## 2.2 Credit Check Doesn't Sum Batched Tool Calls

**Location:** `intentkit/core/middleware.py:222-249`
**Issue:** `CreditCheckMiddleware` checks each tool_call independently against the same balance snapshot. If the LLM requests 3 tool calls each costing 80% of balance, all pass individually even though total exceeds balance.
**Fix:** Sum costs of all tool calls in the message and compare total against balance.

> **User notes:**

---

## 2.3 AgentQuota Counter Race Condition

**Location:** `intentkit/models/agent_data.py:706-724`
**Issue:** `add_message()` does `quota_record.message_count_total += 1` in Python (read-modify-write). Concurrent requests can lose counts. `Chat.add_round()` at line 619 correctly uses server-side `ChatTable.rounds + 1`.
**Fix:** Use SQL server-side expressions: `AgentQuotaTable.message_count_total + 1`.

> **User notes:**

---

## 2.4 `expense_summarize` Hardcoded Wrong CreditType

**Location:** `intentkit/core/credit/expense.py:1021`
**Issue:** Agent fee transaction uses hardcoded `CreditType.REWARD` instead of the dynamically computed `credit_type` variable. `expense_message` and `expense_skill` correctly use computed value. Copy-paste bug causing incorrect credit accounting.
**Fix:** Replace `CreditType.REWARD` with computed `credit_type`.

> **User notes:**

---

## 2.5 Credit Fee Splitting Can Produce Negative Amounts

**Location:** `intentkit/core/credit/expense.py:185-191, 541-549, 864-873`
**Issue:** Independent rounding of fee components with `ROUND_HALF_UP` can make `fee_platform_X + fee_agent_X` exceed original `X_amount`, resulting in negative `base_X_amount`. Could corrupt financial records.
**Fix:** Compute one component as the remainder instead of independent rounding.

> **User notes:**

---

## 2.6 Session Management: No Explicit Rollback on Errors

**Location:** `intentkit/config/db.py:123-146`
**Issue:** `get_session()` context manager only closes the session in `finally`, never rolls back on exceptions. Pending changes after `flush()` but before `commit()` leave transaction state ambiguous.
**Fix:** Add `await session.rollback()` in an `except` block before close.

> **User notes:**

---

## 2.7 Redis Budget Check Non-Atomic (incrbyfloat + expire)

**Location:** `intentkit/core/budget.py:47-48`
**Issue:** `incrbyfloat` and `expire` are two separate Redis commands. Process crash between them leaves a key with no TTL, accumulating indefinitely.
**Fix:** Use a Redis pipeline or Lua script to make the operation atomic.

> **User notes:**

---

## 2.8 Twitter Rate Limit DB-based TOCTOU Race

**Location:** `intentkit/skills/twitter/base.py:56-90`
**Issue:** Rate limiting uses read-modify-write on DB (`get_agent_skill_data` -> increment -> `save_agent_skill_data`). Concurrent requests both pass the check. Compare with the Redis-based `user_rate_limit` which uses atomic `INCR`.
**Fix:** Switch to Redis atomic INCR for rate limiting, consistent with `user_rate_limit`.

> **User notes:**

---

## 2.9 No Foreign Key Constraints Between Core Tables

**Location:** `intentkit/models/agent/db.py`
**Issue:** `AgentTable.owner`, `team_id`, `template_id` reference other tables but have no `ForeignKey` constraints. `AgentDataTable.id` has no FK to `AgentTable.id`. Deleting users/teams creates orphan records. Only `TeamMemberTable` properly uses ForeignKey.
**Fix:** Add ForeignKey constraints with appropriate `ondelete` behavior.

> **User notes:**

---

## 2.10 `Float` Used for Money-Adjacent Fields

**Location:** `models/agent/db.py` — `x402_price` (line 324), `weekly_spending_limit` (lines 92-96)
**Issue:** Float type has precision issues for financial values.
**Fix:** Use `Numeric` (Decimal) type for price and spending limit fields.

> **User notes:**
