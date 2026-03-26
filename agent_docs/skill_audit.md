# Skill Audit Checklist

Tracking document for reviewing and modernizing old skills. Skills ordered by first git commit date (oldest first).

## Common Issues to Check

- **Error handling**: Should raise `ToolException`, not return error strings/dicts
- **Type annotations**: Return types must include `| None` if function can return None
- **Logging**: Use `logger`, not `print()`
- **URLs**: Should be module-level constants, not inline hardcoded
- **Dead code**: Remove unused methods
- **Modern patterns**: `@override` decorator, `{e!s}` format, two-tier exception handling

---

## Batch 1: Initial Skills (2025-06-29) — HIGH PRIORITY

### Critical Issues

| # | Skill | Issue | Severity | Status |
|---|-------|-------|----------|--------|
| 1 | defillama | `base.py`: Dead code — `get_endpoint_url()` (broken `self.base_url`), `format_error_response()` | HIGH | DONE |
| 2 | defillama | `tvl/fetch_protocols.py:138`: `print()` instead of `logger` | MEDIUM | DONE |
| 3 | defillama | All 19 skills + api.py: Returns response with error field instead of raising | HIGH | DONE — api.py refactored with `_get()` helper; all 19 skills now raise `ToolException` |
| 4 | cookiefun | All 5 skill files: Returns error strings instead of raising `ToolException` | HIGH | DONE |
| 5 | cookiefun | `get_sectors.py:29`: Return type mismatch now fixed (raises instead of returning) | MEDIUM | DONE |
| 6 | cryptocompare | `__init__.py:77`: Return type `CryptoCompareBaseTool` but can return `None` | MEDIUM | DONE |
| 7 | cryptocompare | All 6 skills: `raise type(e)(...)` → `raise ToolException(...)` + missing logger | MEDIUM | DONE |
| 8 | dapplooker | `__init__.py:61`: Return type `DappLookerBaseTool` but can return `None` | MEDIUM | DONE |
| 9 | heurist | `__init__.py:85`: Return type `HeuristBaseTool` but can return `None` | MEDIUM | DONE |
| 10 | slack | `__init__.py:59`: Return type `SlackBaseTool` but can return `None` | MEDIUM | DONE |
| 11 | web_scraper | `__init__.py:69`: Return type `WebScraperBaseTool` but can return `None` | MEDIUM | DONE |
| 12 | aixbt | `projects.py:77`: URL hardcoded inline in skill method | LOW | DONE |
| 13 | elfa | `base.py:6`: `base_url` as module-level variable → `ELFA_BASE_URL` constant | LOW | DONE |
| 14 | allora | `base.py:6`: `base_url` as module-level variable → `ALLORA_BASE_URL` constant | LOW | DONE |
| 15 | tavily | `tavily_search.py:92`: URL hardcoded inline → `TAVILY_API_URL` constant | LOW | DONE |
| 16 | lifi | Mixed error handling: `validate_inputs` + skills return strings → raise `ToolException` | LOW | DONE |
| 17 | carv | `_call_carv_api` returns error tuples → raise `ToolException`; all 3 skills updated | LOW | DONE |
| 18 | portfolio | `base.py`: `_run()` uses `asyncio.run()` → removed (base class handles this) | LOW | DONE |

### Skills with No Issues Found (Batch 1)

- twitter — Good error handling, no issues
- cdp — Good error handling, no issues
- dexscreener — Excellent error tuple pattern
- cryptopanic — Consistent `ToolException` usage
- github — Good, public API with rate limit handling
- moralis — Good response pattern
- venice_image — Good, raises `ToolException`
- token — Good, consistent Moralis API usage

---

## Batch 2: Mid-Age Skills (2025-07 to 2025-10) — MEDIUM PRIORITY

| # | Skill | Issue | Severity | Status |
|---|-------|-------|----------|--------|
| 19 | firecrawl | `utils.py:200-201`: Duplicate `@staticmethod` decorator | HIGH | DONE |
| 20 | firecrawl | `crawl.py:365,397`: Returns error strings instead of raising `ToolException` | MEDIUM | DONE |
| 21 | firecrawl | `query.py:126`: `raise type(e)(...)` may fail if exception constructor differs | MEDIUM | DONE |
| 22 | firecrawl | `query.py:49-51`: Dead code — empty try block with `pass` | LOW | DONE |
| 23 | supabase | `__init__.py:66`: Return type should be `SupabaseBaseTool \| None` | LOW | DONE |
| 24 | http | `__init__.py:66`: Return type should be `HttpBaseTool \| None` | LOW | DONE |
| 25 | pyth | `fetch_price.py:42`: Hardcoded Pyth API URL → `PYTH_HERMES_URL` constant | LOW | DONE |

### Skills with No Issues Found (Batch 2)

- xmtp
- basename
- erc20
- erc721
- morpho
- superfluid
- weth
- x402
- casino (minor: hardcoded URLs but acceptable for stable public APIs)

---

## Batch 3: Recent Skills (2026-01 onwards) — LOW PRIORITY

| # | Skill | Issue | Severity | Status |
|---|-------|-------|----------|--------|
| 26 | pancakeswap | `quote.py`, `swap.py`: Returns "No liquidity" error strings | MEDIUM | DONE |
| 27 | pancakeswap | `add_liquidity.py`: Returns "Not staked" error strings + broad `except Exception` | MEDIUM | DONE |

### Skills with No Issues Found (Batch 3)

- jupiter — Good, proper `ToolException` usage, URLs as constants
- ui — Clean, well-written, follows best practices
- image, dune, video — Modern style (2026-03)
- mcp_coingecko — MCP wrapper, auto-generated
- polymarket, uniswap, aerodrome, aave_v3, opensea — Modern style

---

## Progress

- **Total issues found**: 27
- **Fixed**: 27
- **Skipped**: 0
- **Remaining**: 0

## Files Modified

~55 files across 16 skill categories:
- defillama: base.py, tvl/fetch_protocols.py
- cookiefun: get_sectors.py, get_account_details.py, get_account_feed.py, get_account_smart_followers.py, search_accounts.py
- firecrawl: utils.py, crawl.py, query.py
- cryptocompare, dapplooker, heurist, slack, web_scraper, supabase, http: __init__.py
- aixbt: base.py, projects.py
- elfa: base.py, utils.py
- allora: base.py, price.py
- tavily: tavily_search.py
- pyth: fetch_price.py
- portfolio: base.py
- carv: base.py, fetch_news.py, onchain_query.py, token_info_and_price.py
- lifi: utils.py, token_quote.py, token_execute.py
- pancakeswap: quote.py, swap.py, add_liquidity.py
- cryptocompare: fetch_news.py, fetch_price.py, fetch_top_exchanges.py, fetch_top_market_cap.py, fetch_top_volume.py, fetch_trading_signals.py
- defillama (full refactor): api.py + all 19 skill files across coins/, tvl/, stablecoins/, yields/, volumes/, fees/
