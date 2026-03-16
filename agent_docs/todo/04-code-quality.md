# Priority 4: Code Quality & Architecture

These are correctness issues, anti-patterns, and technical debt that should be addressed.

---

## 4.1 Import Dependency Violations in utils/

**Location:** `intentkit/utils/s3_setup.py:6-7` (imports from `clients` and `config`), `intentkit/utils/ens.py:12-13` (imports from `config`)
**Issue:** Project rule: `utils -> config -> models -> abstracts -> clients -> skills -> core` (left cannot import right). `s3_setup.py` reaches all the way to `clients`.
**Fix:** Move `s3_setup.py` to `clients/` and `ens.py` to a higher layer, or inject dependencies.

> **User notes:**

---

## 4.2 Pydantic V2 Deprecated `json_encoders` in 11 Files

**Location:** `chat.py`, `skill.py`, `credit/price.py`, `app_setting.py`, `llm.py`, `user.py`, `credit/event.py`, `credit/account.py`, `credit/transaction.py`, `team.py`, `agent/response.py`
**Issue:** `json_encoders` in `ConfigDict` is deprecated in Pydantic V2.
**Fix:** Replace with `@field_serializer` decorators.

> **User notes:**

---

## 4.3 Credit Expense Massive Code Duplication

**Location:** `intentkit/core/credit/expense.py`
**Issue:** `expense_message`, `expense_skill`, `expense_summarize` share ~80% identical code (~200 lines each for fee calculation, credit type splitting, transaction creation). The `CreditType.REWARD` bug (#2.4) exists only in `expense_summarize`, showing how divergence creeps in.
**Fix:** Extract shared fee calculation and transaction creation into a common helper.

> **User notes:**

---

## 4.4 Telegram Entrypoint Prompt Silently Overwritten

**Location:** `intentkit/core/prompt.py:352-356`
**Issue:** When both `config.tg_system_prompt` and `agent.telegram_entrypoint_prompt` are set, the system-level prompt is assigned then immediately overwritten by agent-level. Same for XMTP (lines 357-361).
**Fix:** Concatenate both prompts, or document the override-not-merge behavior.

> **User notes:**

---

## 4.5 Skill Error Handling Inconsistency

**Location:** Multiple skills — `github/github_search.py:168-175`, `tavily/tavily_search.py:138-140`, `firecrawl/scrape.py:420-427`, `casino/dice_roll.py:94-96`, `moralis/api.py:37-60`
**Issue:** Some skills return error strings, others return error dicts, others raise exceptions. The skill development guide says "just raise it". LLM may interpret error strings as valid results.
**Fix:** Standardize: all skills should raise exceptions on errors, per the dev guide.

> **User notes:**

---

## 4.6 `call_agent` No Recursion Depth Protection

**Location:** `intentkit/core/system_skills/call_agent.py`
**Issue:** Agent A can call Agent B which calls A — infinite recursion. Only guard is 300s timeout which wastes significant resources before triggering.
**Fix:** Add depth counter to `AgentContext`, reject calls beyond a configurable limit.

> **User notes:**

---

## 4.7 TemplateTable Default Model Hardcoded

**Location:** `intentkit/models/template.py:73`
**Issue:** Default model hardcoded as `"gpt-5-mini"` while `AgentCore` uses dynamic `pick_default_model()`. If default model changes, templates silently use invalid model.
**Fix:** Use `pick_default_model()` or a shared constant.

> **User notes:**

---

## 4.8 `_credit_per_usdc` Global Cache Never Expires

**Location:** `intentkit/models/llm.py:32`
**Issue:** Once set, never cleared or refreshed. Runtime DB updates to `credit_per_usdc` are ignored for the process lifetime.
**Fix:** Add TTL-based refresh or read from a cached `AppSetting`.

> **User notes:**

---

## 4.9 `CreditEvent` Raises HTTPException in Model Layer

**Location:** `intentkit/models/credit/event.py:536`
**Issue:** Model-layer function raises `fastapi.HTTPException` instead of a domain error. Violates layer separation.
**Fix:** Raise `IntentKitAPIError` or a domain-specific exception.

> **User notes:**

---

## 4.10 Detached ORM Instance Access After Session Close

**Location:** `intentkit/core/agent/queries.py:24-35, 93-97`
**Issue:** `item.template_id` accessed after `async with get_session()` block exits. SQLAlchemy ORM instance may raise `DetachedInstanceError` for lazy-loaded attributes.
**Fix:** Access all needed attributes within the session scope, or use `expire_on_commit=False`.

> **User notes:**

---

## 4.11 Supabase Filter Logic Duplicated Across Skills

**Location:** `skills/supabase/fetch_data.py:68-95`, `delete_data.py:61-87`, `update_data.py`
**Issue:** Filter application logic (eq, neq, gt, gte, lt, lte, like, ilike, in) copy-pasted identically.
**Fix:** Extract into a shared method in `SupabaseBaseTool`.

> **User notes:**

---

## 4.12 Firecrawl Accesses FAISS Private `_dict` Attribute

**Location:** `intentkit/skills/firecrawl/scrape.py:286-293`
**Issue:** Directly accesses `existing_vector_store.docstore._dict` — private internal attribute. Fragile, may break on library updates.
**Fix:** Use public API or a more robust approach.

> **User notes:**

---

## 4.13 Silently Swallowed Exceptions

**Location:** `utils/opengraph.py:107`, `utils/slack_alert.py:79`, `utils/s3_setup.py:80-82`, `skills/base.py:318-321`
**Issue:** Multiple `except Exception: return None` or `except Exception: pass` blocks silently discard errors with no logging. Programming bugs hidden.
**Fix:** Add logging at minimum. For `build_skill_prices`, log the import error so broken skills are noticed.

> **User notes:**

---

## 4.14 OpenAI Streaming Endpoint is Fake Streaming

**Location:** `app/entrypoints/agent_api.py:1180-1227`
**Issue:** First runs full `execute_agent()`, then streams the complete result in 20-char chunks. User gets no benefit from streaming — all latency is upfront.
**Fix:** Implement true streaming using `stream_agent`, or document the limitation.

> **User notes:**

---

## 4.15 Missing Slack Cleanup

**Location:** `intentkit/utils/alert.py:82-94`
**Issue:** `cleanup_alert()` handles Telegram cleanup but not Slack. `WebClient` may hold connections never closed.
**Fix:** Add `cleanup_slack()` and call it from `cleanup_alert()`.

> **User notes:**

---

## 4.16 Slack `init_slack` Missing Input Validation

**Location:** `intentkit/utils/slack_alert.py:20-35`
**Issue:** Unlike `init_telegram` which validates non-empty token/chat_id, `init_slack` does not validate `token` and `channel`.
**Fix:** Add non-empty validation, consistent with Telegram.

> **User notes:**
