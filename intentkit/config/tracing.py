"""Langfuse tracing setup.

Langfuse needs a callback handler, so we register that handler through
LangChain's global configure-hook — the same mechanism LangChain's own tracer
uses internally. Once registered, the handler is added to every run's callback
manager automatically, with no per-invocation wiring.

Tracing is enabled only when both Langfuse keys are configured (see
``config.py``); otherwise agents run without it.
"""

import logging
from contextvars import ContextVar
from typing import Any, Callable

logger = logging.getLogger(__name__)

# The hook reads this contextvar in whatever context a run executes. Setup runs
# at import time (root context), but the agent loop may run in a different
# thread/context, so we cannot rely on a ``.set()`` value propagating there.
# Instead the handler becomes the contextvar's *default*, which ``.get()``
# returns in every context — async tasks, worker threads, fresh contexts alike.
# The var is therefore (re)created in setup with the handler baked in as default.
_langfuse_handler_var: ContextVar[Any] | None = None
_hook_registered = False

# Resolver returning the USD cost of a finished LangChain LLM run. Registered by
# ``intentkit.models.llm`` so this config-layer module can price generations
# without importing the model catalog (which sits above config in the layering).
_cost_resolver: Callable[[Any], float | None] | None = None


def set_generation_cost_resolver(resolver: Callable[[Any], float | None]) -> None:
    """Register the function used to price LLM generations for Langfuse."""
    global _cost_resolver
    _cost_resolver = resolver


def _apply_cost_details(runs: Any, run_id: Any, response: Any) -> None:
    """Attach our computed cost to the live Langfuse generation for this run.

    Langfuse's LangChain handler only sends token usage and lets the server
    infer cost from its own model prices (which misprice Gemini cache-read and
    ignore OpenRouter's real charge). We instead set ``cost_details`` on the
    still-open generation — looked up by ``run_id`` just before the base handler
    ends it — and ingested cost takes precedence over inferred cost server-side.
    Best effort: a failure here must never break the run.
    """
    resolver = _cost_resolver
    if resolver is None:
        return
    try:
        generation = runs.get(run_id)
        if generation is None:
            return
        cost = resolver(response)
        if cost is not None:
            generation.update(cost_details={"total": cost})
    except Exception:
        logger.warning("Failed to attach cost to Langfuse generation", exc_info=True)


def _build_cost_forwarding_handler(base_cls: Any) -> Any:
    """Build the Langfuse callback handler that also forwards our cost.

    Subclasses the stock handler to set ``cost_details`` in ``on_llm_end``. The
    base class is only importable after the lazy import in ``setup_langfuse``,
    so the subclass is defined here rather than at module top.
    """

    class _CostForwardingHandler(base_cls):
        def on_llm_end(self, response, *, run_id, parent_run_id=None, **kwargs):
            _apply_cost_details(self._runs, run_id, response)
            return super().on_llm_end(
                response, run_id=run_id, parent_run_id=parent_run_id, **kwargs
            )

    return _CostForwardingHandler()


def setup_langfuse(
    *,
    public_key: str,
    secret_key: str,
    base_url: str | None,
    environment: str,
    release: str | None,
) -> bool:
    """Initialize the global Langfuse client and attach its LangChain handler.

    The handler is wired through ``register_configure_hook`` so LangChain adds
    it to every callback manager it builds — covering agent runs and every
    ad-hoc LLM call without touching their call sites.

    Runs once per process: the first call configures the client, builds the
    handler and registers the hook; later calls are no-ops (so the client and
    its background threads are never rebuilt). Returns ``True`` when Langfuse
    tracing is active.
    """
    global _langfuse_handler_var, _hook_registered
    if _hook_registered:
        return True
    try:
        from langchain_core.tracers.context import register_configure_hook
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler
    except ImportError:
        logger.warning("langfuse not installed; Langfuse tracing disabled")
        return False

    # Configure the process-wide Langfuse singleton from the sanitized config
    # values. The handler resolves this client via get_client().
    _ = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        base_url=base_url,
        environment=environment,
        release=release,
        tracing_enabled=True,
    )

    # Handler as contextvar default => attaches to runs in any context/thread.
    _langfuse_handler_var = ContextVar(
        "langfuse_callback_handler",
        default=_build_cost_forwarding_handler(CallbackHandler),
    )
    register_configure_hook(_langfuse_handler_var, True)
    _hook_registered = True
    logger.info("Langfuse tracing enabled (base_url=%s)", base_url or "default")
    return True
