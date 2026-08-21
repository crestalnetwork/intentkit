"""Catalog hygiene for the built-in web search tool."""

from pathlib import Path

import yaml as pyyaml

import intentkit.models.llm as llm_module
from intentkit.core.system_tools.search_web import _GEMINI_SEARCH_MODEL


def test_gemini_search_model_is_a_live_catalog_id():
    """The grounding fallback hardcodes a Gemini id; legacy_ids routing would
    mask a retired one, so pin it to a live catalog entry like the pickers."""
    rows = pyyaml.safe_load(
        Path(llm_module.__file__).with_name("llm.yaml").read_text(encoding="utf-8")
    )
    live = {row["id"] for row in rows if row["provider"] == "google"}
    assert _GEMINI_SEARCH_MODEL in live
