"""tools config becomes a flat name list (idempotent)

``agents.tools`` and ``templates.tools`` change shape from
``{category: {enabled, states: {tool: disabled|public|private}}}`` to a flat
``["tool_name", ...]`` list. The public/private distinction is gone — agents
are neutral and expose the same tools to every caller. A tool is kept when
its category was enabled and its state was ``public`` or ``private``.

Idempotent: rows already holding a list are left untouched, so re-running is
always safe.

Revision ID: c4e8a1f6d2b9
Revises: b7f2c9d4a1e8
Create Date: 2026-07-05 00:00:00.000000

"""

import json
import logging
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = "c4e8a1f6d2b9"
down_revision: Union[str, Sequence[str], None] = "b7f2c9d4a1e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Categories whose legacy state keys differ from the canonical tool names.
# Generated from the tool registry at refactor time.
_LEGACY_NAME_MAP: dict[str, dict[str, str]] = {
    "aerodrome": {
        "quote": "aerodrome_quote",
        "swap": "aerodrome_swap",
        "get_positions": "aerodrome_get_positions",
        "add_liquidity": "aerodrome_add_liquidity",
        "remove_liquidity": "aerodrome_remove_liquidity",
    },
    "allora": {
        "get_price_prediction": "allora_get_price_prediction",
    },
    "carv": {
        "onchain_query": "carv_onchain_query",
        "token_info_and_price": "carv_token_info_and_price",
        "fetch_news": "carv_fetch_news",
    },
    "casino": {
        "deck_shuffle": "casino_deck_shuffle",
        "deck_draw": "casino_deck_draw",
        "dice_roll": "casino_dice_roll",
    },
    "cn_stock": {
        "get_quote": "cn_stock_get_quote",
        "get_kline": "cn_stock_get_kline",
        "get_index": "cn_stock_get_index",
        "get_board": "cn_stock_get_board",
        "get_capital_flow": "cn_stock_get_capital_flow",
        "get_news": "cn_stock_get_news",
        "get_announcement": "cn_stock_get_announcement",
        "get_financials": "cn_stock_get_financials",
        "is_trading_day": "cn_stock_is_trading_day",
    },
    "cookiefun": {
        "get_sectors": "cookiefun_get_sectors",
        "get_account_details": "cookiefun_get_account_details",
        "get_account_smart_followers": "cookiefun_get_account_smart_followers",
        "search_accounts": "cookiefun_search_accounts",
        "get_account_feed": "cookiefun_get_account_feed",
    },
    "cryptocompare": {
        "fetch_news": "cryptocompare_fetch_news",
        "fetch_price": "cryptocompare_fetch_price",
        "fetch_trading_signals": "cryptocompare_fetch_trading_signals",
        "fetch_top_market_cap": "cryptocompare_fetch_top_market_cap",
        "fetch_top_exchanges": "cryptocompare_fetch_top_exchanges",
        "fetch_top_volume": "cryptocompare_fetch_top_volume",
    },
    "defillama": {
        "fetch_batch_historical_prices": "defillama_fetch_batch_historical_prices",
        "fetch_block": "defillama_fetch_block",
        "fetch_current_prices": "defillama_fetch_current_prices",
        "fetch_first_price": "defillama_fetch_first_price",
        "fetch_historical_prices": "defillama_fetch_historical_prices",
        "fetch_price_chart": "defillama_fetch_price_chart",
        "fetch_price_percentage": "defillama_fetch_price_percentage",
        "fetch_fees_overview": "defillama_fetch_fees_overview",
        "fetch_stablecoin_chains": "defillama_fetch_stablecoin_chains",
        "fetch_stablecoin_charts": "defillama_fetch_stablecoin_charts",
        "fetch_stablecoin_prices": "defillama_fetch_stablecoin_prices",
        "fetch_stablecoins": "defillama_fetch_stablecoins",
        "fetch_chain_historical_tvl": "defillama_fetch_chain_historical_tvl",
        "fetch_chains": "defillama_fetch_chains",
        "fetch_historical_tvl": "defillama_fetch_total_historical_tvl",
        "fetch_protocol": "defillama_fetch_protocol",
        "fetch_protocol_current_tvl": "defillama_fetch_protocol_tvl",
        "fetch_protocols": "defillama_fetch_protocols",
        "fetch_dex_overview": "defillama_fetch_dex_overview",
        "fetch_dex_summary": "defillama_fetch_dex_summary",
        "fetch_options_overview": "defillama_fetch_options_overview",
        "fetch_pool_chart": "defillama_fetch_pool_chart",
        "fetch_pools": "defillama_fetch_pools",
    },
    "dexscreener": {
        "search_token": "dexscreener_search_token",
        "get_pair_info": "dexscreener_get_pair_info",
        "get_token_pairs": "dexscreener_get_token_pairs",
        "get_tokens_info": "dexscreener_get_tokens_info",
    },
    "elfa": {
        "get_top_mentions": "elfa_get_top_mentions",
        "search_mentions": "elfa_search_mentions",
        "get_trending_tokens": "elfa_get_trending_tokens",
        "get_smart_stats": "elfa_get_smart_stats",
    },
    "enso": {
        "get_networks": "enso_get_networks",
        "get_tokens": "enso_get_tokens",
        "get_prices": "enso_get_prices",
        "get_wallet_approvals": "enso_get_wallet_approvals",
        "get_wallet_balances": "enso_get_wallet_balances",
        "wallet_approve": "enso_wallet_approve",
        "route_shortcut": "enso_route_shortcut",
        "get_best_yield": "enso_get_best_yield",
    },
    "lifi": {
        "token_quote": "lifi_token_quote",
        "token_execute": "lifi_token_execute",
    },
    "moralis": {
        "fetch_wallet_portfolio": "moralis_fetch_wallet_portfolio",
        "fetch_chain_portfolio": "moralis_fetch_chain_portfolio",
        "fetch_nft_portfolio": "moralis_fetch_nft_portfolio",
        "fetch_solana_portfolio": "moralis_fetch_solana_portfolio",
    },
    "pancakeswap": {
        "quote": "pancakeswap_quote",
        "swap": "pancakeswap_swap",
        "get_positions": "pancakeswap_get_positions",
        "add_liquidity": "pancakeswap_add_liquidity",
        "remove_liquidity": "pancakeswap_remove_liquidity",
    },
    "polymarket": {
        "search_markets": "polymarket_search_markets",
        "get_market": "polymarket_get_market",
        "get_orderbook": "polymarket_get_orderbook",
        "get_price_history": "polymarket_get_price_history",
        "place_order": "polymarket_place_order",
        "cancel_order": "polymarket_cancel_order",
        "get_positions": "polymarket_get_positions",
        "get_orders": "polymarket_get_orders",
        "get_trades": "polymarket_get_trades",
    },
    "portfolio": {
        "wallet_history": "portfolio_wallet_history",
        "token_balances": "portfolio_token_balances",
        "wallet_approvals": "portfolio_wallet_approvals",
        "wallet_swaps": "portfolio_wallet_swaps",
        "wallet_net_worth": "portfolio_wallet_net_worth",
        "wallet_profitability_summary": "portfolio_wallet_profitability_summary",
        "wallet_profitability": "portfolio_wallet_profitability",
        "wallet_stats": "portfolio_wallet_stats",
        "wallet_defi_positions": "portfolio_wallet_defi_positions",
        "wallet_nfts": "portfolio_wallet_nfts",
    },
    "uniswap": {
        "quote": "uniswap_quote",
        "swap": "uniswap_swap",
        "get_positions": "uniswap_get_positions",
        "add_liquidity": "uniswap_add_liquidity",
        "remove_liquidity": "uniswap_remove_liquidity",
    },
    "venice_audio": {
        "text_to_speech": "venice_audio_text_to_speech",
    },
    "venice_image": {
        "image_vision": "venice_image_vision",
        "image_enhance": "venice_image_enhance",
        "image_upscale": "venice_image_upscale",
        "image_generation_flux_dev": "venice_image_generation_flux_dev",
        "image_generation_flux_dev_uncensored": "venice_image_generation_flux_dev_uncensored",
        "image_generation_venice_sd35": "venice_image_generation_venice_sd35",
        "image_generation_fluently_xl": "venice_image_generation_fluently_xl",
        "image_generation_lustify_sdxl": "venice_image_generation_lustify_sdxl",
        "image_generation_pony_realism": "venice_image_generation_pony_realism",
        "image_generation_stable_diffusion_3_5": "venice_image_generation_stable_diffusion_3_5",
    },
    "web_scraper": {
        "scrape_and_index": "web_scraper_scrape_and_index",
        "query_indexed_content": "web_scraper_query_indexed_content",
        "website_indexer": "web_scraper_website_indexer",
        "document_indexer": "web_scraper_document_indexer",
    },
}


def _to_name_list(tools: Any) -> list[str] | None:
    """Convert a legacy tools dict to a name list; None when nothing enabled."""
    if not isinstance(tools, dict):
        return None
    names: list[str] = []
    for category, config in tools.items():
        if not isinstance(config, dict) or not config.get("enabled"):
            continue
        states = config.get("states")
        if not isinstance(states, dict):
            continue
        rename = _LEGACY_NAME_MAP.get(category, {})
        for tool_name, state in states.items():
            if state not in ("public", "private"):
                continue
            canonical = rename.get(tool_name, tool_name)
            if canonical not in names:
                names.append(canonical)
    return names or None


def _convert_table(bind: sa.Connection, table: str) -> None:
    rows = bind.execute(
        sa.text(
            f"SELECT id, tools FROM {table} "
            "WHERE tools IS NOT NULL AND jsonb_typeof(tools) = 'object'"
        )
    ).all()

    converted = 0
    for row in rows:
        tools = row.tools
        if isinstance(tools, str):
            try:
                tools = json.loads(tools)
            except json.JSONDecodeError:
                logger.warning("Skipping %s %s: unparsable tools", table, row.id)
                continue
        names = _to_name_list(tools)
        bind.execute(
            sa.text(f"UPDATE {table} SET tools = CAST(:tools AS jsonb) WHERE id = :id"),
            {"tools": json.dumps(names), "id": row.id},
        )
        converted += 1

    logger.info("Converted %s %s rows to tools name lists", converted, table)


def upgrade() -> None:
    """Upgrade data (idempotent — list-shaped rows are not selected)."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for table in ("agents", "templates"):
        if insp.has_table(table):
            _convert_table(bind, table)


def downgrade() -> None:
    """Irreversible: the tri-state visibility information is discarded."""
    # Intentionally a no-op; list-shaped configs simply remain in place.
