"""Langfuse tracing setup.

Langfuse needs a callback handler, so we register that handler through
LangChain's global configure-hook — the same mechanism LangChain's own tracer
uses internally. Once registered, the handler is added to every run's callback
manager automatically, with no per-invocation wiring.

Tracing is enabled only when both Langfuse keys are configured (see
``config.py``); otherwise agents run without it.
"""

import logging
import sys
import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

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


class _TurnUsage:
    """Accumulated LLM token usage for one live trace (one chat turn)."""

    __slots__ = ("cached_tokens", "input_tokens", "owner_run_id")

    def __init__(self, owner_run_id: Any) -> None:
        self.owner_run_id = owner_run_id
        self.input_tokens = 0
        self.cached_tokens = 0


# Live turn accumulators keyed by Langfuse trace id. The first root chain run
# observed for a trace claims it (should another root run land in the same
# trace, e.g. a delegated sub-agent run nesting into the caller's trace, it
# must not reclaim it); every LLM call in the trace adds its usage; the
# owner's chain-end emits the turn-level score and removes the entry.
# LangChain may run sync callbacks in worker threads, hence the lock.
_turn_usage: dict[str, _TurnUsage] = {}
_turn_usage_lock = threading.Lock()
# A turn that dies without end/error callbacks (e.g. hard cancellation) would
# leak its entry; cap the dict and evict the oldest entries past the cap.
_MAX_TRACKED_TURNS = 256


def _extract_llm_usage(response: Any) -> tuple[int, int]:
    """Sum ``(input_tokens, cache_read_tokens)`` over a finished LLM run.

    ``input_tokens`` follows LangChain's convention: the full prompt size,
    cache reads included — so ``cache_read / input`` is the hit rate.
    """
    input_tokens = 0
    cached_tokens = 0
    for generations in getattr(response, "generations", None) or []:
        for generation in generations or []:
            usage = getattr(
                getattr(generation, "message", None), "usage_metadata", None
            )
            if not usage:
                continue
            input_tokens += usage.get("input_tokens") or 0
            details = usage.get("input_token_details")
            if isinstance(details, dict):
                cached_tokens += details.get("cache_read") or 0
    return input_tokens, cached_tokens


def _hit_rate(cached_tokens: int, input_tokens: int) -> float:
    """Cache hit rate clamped to [0, 1] against malformed provider counts."""
    return min(1.0, max(0.0, cached_tokens / input_tokens))


def _track_turn_start(runs: Any, run_id: Any) -> None:
    """Claim the trace for this root chain run so its LLM usage is accumulated."""
    try:
        trace_id = getattr(runs.get(run_id), "trace_id", None)
        if trace_id is None:
            return
        evicted = 0
        with _turn_usage_lock:
            if trace_id in _turn_usage:
                return
            while len(_turn_usage) >= _MAX_TRACKED_TURNS:
                _turn_usage.pop(next(iter(_turn_usage)))
                evicted += 1
            _turn_usage[trace_id] = _TurnUsage(run_id)
        if evicted:
            logger.warning(
                "Evicted %d tracked turn(s); their turn-level cache scores are lost",
                evicted,
            )
    except Exception:
        logger.warning("Failed to track Langfuse turn start", exc_info=True)


def _apply_cache_hit_rate(runs: Any, run_id: Any, response: Any) -> None:
    """Score cache hit rate on the generation and add its usage to the turn."""
    try:
        generation = runs.get(run_id)
        if generation is None:
            return
        input_tokens, cached_tokens = _extract_llm_usage(response)
        if input_tokens <= 0:
            return
        generation.score(
            name="generation_cache_hit_rate",
            value=_hit_rate(cached_tokens, input_tokens),
            data_type="NUMERIC",
            comment=f"cache_read={cached_tokens}, input={input_tokens}",
        )
        trace_id = getattr(generation, "trace_id", None)
        if trace_id is None:
            return
        with _turn_usage_lock:
            turn = _turn_usage.get(trace_id)
            if turn is not None:
                turn.input_tokens += input_tokens
                turn.cached_tokens += cached_tokens
    except Exception:
        logger.warning("Failed to score generation cache hit rate", exc_info=True)


def _finish_turn(runs: Any, run_id: Any) -> None:
    """Emit the turn-level cache-hit-rate score if this run owns its trace."""
    try:
        observation = runs.get(run_id)
        trace_id = getattr(observation, "trace_id", None)
        if trace_id is None:
            return
        with _turn_usage_lock:
            turn = _turn_usage.get(trace_id)
            if turn is None or turn.owner_run_id != run_id:
                return
            del _turn_usage[trace_id]
        if turn.input_tokens > 0:
            observation.score_trace(
                name="turn_cache_hit_rate",
                value=_hit_rate(turn.cached_tokens, turn.input_tokens),
                data_type="NUMERIC",
                comment=f"cache_read={turn.cached_tokens}, input={turn.input_tokens}",
            )
    except Exception:
        logger.warning("Failed to score turn cache hit rate", exc_info=True)


def _build_cost_forwarding_handler(base_cls: Any) -> Any:
    """Build the Langfuse callback handler with our cost and cache enrichment.

    Subclasses the stock handler to set ``cost_details`` and score cache hit
    rates: per generation in ``on_llm_end``, and per turn (trace) when the
    root chain run that opened the trace ends. The base class is only
    importable after the lazy import in ``setup_langfuse``, so the subclass is
    defined here rather than at module top.
    """

    class _CostForwardingHandler(base_cls):
        def on_chain_start(
            self, serialized, inputs, *, run_id, parent_run_id=None, **kwargs
        ):
            result = super().on_chain_start(
                serialized,
                inputs,
                run_id=run_id,
                parent_run_id=parent_run_id,
                **kwargs,
            )
            if parent_run_id is None:
                _track_turn_start(self._runs, run_id)
            return result

        def on_llm_end(self, response, *, run_id, parent_run_id=None, **kwargs):
            _apply_cost_details(self._runs, run_id, response)
            _apply_cache_hit_rate(self._runs, run_id, response)
            return super().on_llm_end(
                response, run_id=run_id, parent_run_id=parent_run_id, **kwargs
            )

        def on_chain_end(self, outputs, *, run_id, parent_run_id=None, **kwargs):
            if parent_run_id is None:
                _finish_turn(self._runs, run_id)
            return super().on_chain_end(
                outputs, run_id=run_id, parent_run_id=parent_run_id, **kwargs
            )

        def on_chain_error(self, error, *, run_id, parent_run_id=None, **kwargs):
            if parent_run_id is None:
                _finish_turn(self._runs, run_id)
            return super().on_chain_error(
                error, run_id=run_id, parent_run_id=parent_run_id, **kwargs
            )

    return _CostForwardingHandler()


@contextmanager
def propagate_trace_attributes(
    *, session_id: str | None = None, user_id: str | None = None
) -> Generator[None]:
    """Propagate Langfuse session/user to every span created inside.

    The Langfuse LangChain handler applies ``langfuse_session_id`` /
    ``langfuse_user_id`` metadata by entering its propagation context inside
    the root ``on_chain_start`` callback — which LangChain may run in a copied
    context, so the attributes reach the root span only and every child
    observation is left without session/user (breaking observation-level
    analytics like usage grouped by session). Wrapping the whole agent run
    here puts the attributes in the run's own context instead, covering every
    observation. No-op when tracing is disabled; must never break the run.
    """
    if not _hook_registered:
        yield
        return
    try:
        from langfuse import propagate_attributes

        cm = propagate_attributes(session_id=session_id, user_id=user_id)
        cm.__enter__()
    except Exception:
        logger.warning("Failed to propagate Langfuse trace attributes", exc_info=True)
        yield
        return
    try:
        yield
    finally:
        try:
            _ = cm.__exit__(*sys.exc_info())
        except Exception:
            logger.warning("Failed to detach Langfuse trace attributes", exc_info=True)


def record_conversation_cache_hit_rate(
    *, session_id: str, input_tokens: int, cached_tokens: int
) -> None:
    """Upsert the conversation-level cache-hit-rate score for a session.

    Uses a deterministic score id so each turn overwrites the previous value
    instead of stacking one score per turn. Best effort: a failure here must
    never break the run.
    """
    if not _hook_registered or input_tokens <= 0:
        return
    try:
        from langfuse import get_client

        get_client().create_score(
            name="conversation_cache_hit_rate",
            value=_hit_rate(cached_tokens, input_tokens),
            session_id=session_id,
            score_id=f"conv-cache-hit-{session_id}",
            data_type="NUMERIC",
            comment=f"cache_read={cached_tokens}, input={input_tokens}",
        )
    except Exception:
        logger.warning("Failed to record conversation cache hit rate", exc_info=True)


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
    # The single shared handler instance is deliberate — per-run state lives in
    # Langfuse's own context, not on the handler.
    _langfuse_handler_var = ContextVar(
        "langfuse_callback_handler",
        default=_build_cost_forwarding_handler(CallbackHandler),  # noqa: B039
    )
    register_configure_hook(_langfuse_handler_var, True)
    _hook_registered = True
    logger.info("Langfuse tracing enabled (base_url=%s)", base_url or "default")
    return True
