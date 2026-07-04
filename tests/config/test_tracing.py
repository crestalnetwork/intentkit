"""Tests for Langfuse tracing setup (intentkit.config.tracing)."""

import pytest

from intentkit.config import tracing


class _FakeGeneration:
    def __init__(self):
        self.cost_details = None

    def update(self, *, cost_details=None, **kwargs):
        self.cost_details = cost_details
        return self


@pytest.fixture
def restore_resolver():
    saved = tracing._cost_resolver
    yield
    tracing._cost_resolver = saved


def test_apply_cost_details_sets_cost_on_generation(restore_resolver):
    gen = _FakeGeneration()
    tracing.set_generation_cost_resolver(lambda response: 0.0042)

    tracing._apply_cost_details({"r1": gen}, "r1", object())

    assert gen.cost_details == {"total": 0.0042}


def test_apply_cost_details_noop_when_resolver_returns_none(restore_resolver):
    gen = _FakeGeneration()
    tracing.set_generation_cost_resolver(lambda response: None)

    tracing._apply_cost_details({"r1": gen}, "r1", object())

    assert gen.cost_details is None


def test_apply_cost_details_noop_when_run_missing(restore_resolver):
    tracing.set_generation_cost_resolver(lambda response: 1.0)
    # No generation for this run_id => nothing happens, no error.
    tracing._apply_cost_details({}, "missing", object())


def test_apply_cost_details_survives_resolver_error(restore_resolver):
    gen = _FakeGeneration()

    def boom(response):
        raise RuntimeError("resolver blew up")

    tracing.set_generation_cost_resolver(boom)

    # Best effort: a resolver error must not propagate out of the callback.
    tracing._apply_cost_details({"r1": gen}, "r1", object())
    assert gen.cost_details is None


def test_apply_cost_details_noop_when_no_resolver(restore_resolver):
    tracing._cost_resolver = None
    gen = _FakeGeneration()
    tracing._apply_cost_details({"r1": gen}, "r1", object())
    assert gen.cost_details is None


class _FakeLangfuse:
    instances: list[dict] = []

    def __init__(self, **kwargs):
        _FakeLangfuse.instances.append(kwargs)


class _FakeHandler:
    created = 0

    def __init__(self, *args, **kwargs):
        _FakeHandler.created += 1


def _reset(monkeypatch):
    """Reset module + fake state so each test starts from a clean process."""
    _FakeLangfuse.instances = []
    _FakeHandler.created = 0
    monkeypatch.setattr(tracing, "_hook_registered", False)
    monkeypatch.setattr(tracing, "_langfuse_handler_var", None)

    registered: list = []
    monkeypatch.setattr("langfuse.Langfuse", _FakeLangfuse)
    monkeypatch.setattr("langfuse.langchain.CallbackHandler", _FakeHandler)
    monkeypatch.setattr(
        "langchain_core.tracers.context.register_configure_hook",
        lambda *a, **k: registered.append((a, k)),
    )
    return registered


def test_setup_langfuse_initializes_client_and_handler(monkeypatch):
    registered = _reset(monkeypatch)

    result = tracing.setup_langfuse(
        public_key="pk-test",
        secret_key="sk-test",
        base_url="https://example.langfuse.test",
        environment="local",
        release="v1.2.3",
    )

    assert result is True
    # Client constructed with the sanitized config values.
    assert _FakeLangfuse.instances == [
        {
            "public_key": "pk-test",
            "secret_key": "sk-test",
            "base_url": "https://example.langfuse.test",
            "environment": "local",
            "release": "v1.2.3",
            "tracing_enabled": True,
        }
    ]
    # Hook registered once, with the handler living as the contextvar default so
    # it attaches to runs in any context/thread.
    assert len(registered) == 1
    assert _FakeHandler.created == 1
    assert tracing._langfuse_handler_var is not None
    assert isinstance(tracing._langfuse_handler_var.get(), _FakeHandler)
    # The registered hook points at the same contextvar the handler lives in.
    assert registered[0][0][0] is tracing._langfuse_handler_var


class _FakeUsageMessage:
    def __init__(self, usage):
        self.usage_metadata = usage


class _FakeChatGeneration:
    def __init__(self, usage):
        self.message = _FakeUsageMessage(usage)


class _FakeLLMResult:
    def __init__(self, *usages):
        self.generations = [[_FakeChatGeneration(u) for u in usages]]


class _FakeObservation:
    """Stands in for the Langfuse span/generation wrapper stored in _runs."""

    def __init__(self, trace_id="trace-1"):
        self.trace_id = trace_id
        self.scores: list[dict] = []
        self.trace_scores: list[dict] = []

    def score(self, **kwargs):
        self.scores.append(kwargs)

    def score_trace(self, **kwargs):
        self.trace_scores.append(kwargs)


@pytest.fixture(autouse=True)
def clear_turn_usage():
    tracing._turn_usage.clear()
    yield
    tracing._turn_usage.clear()


def test_extract_llm_usage_sums_generations():
    response = _FakeLLMResult(
        {"input_tokens": 100, "input_token_details": {"cache_read": 40}},
        {"input_tokens": 50},
        None,  # generation without usage_metadata
    )

    assert tracing._extract_llm_usage(response) == (150, 40)


def test_cache_hit_rate_turn_lifecycle():
    root = _FakeObservation()
    generation = _FakeObservation()
    runs = {"root": root, "llm": generation}

    tracing._track_turn_start(runs, "root")
    tracing._apply_cache_hit_rate(
        runs,
        "llm",
        _FakeLLMResult(
            {"input_tokens": 200, "input_token_details": {"cache_read": 50}}
        ),
    )
    tracing._apply_cache_hit_rate(
        runs,
        "llm",
        _FakeLLMResult(
            {"input_tokens": 100, "input_token_details": {"cache_read": 100}}
        ),
    )
    tracing._finish_turn(runs, "root")

    # Every LLM call gets its own generation-level score.
    assert [s["name"] for s in generation.scores] == ["generation_cache_hit_rate"] * 2
    assert generation.scores[0]["value"] == 0.25
    assert generation.scores[1]["value"] == 1.0
    # The turn score aggregates both calls: 150 cached / 300 input.
    assert root.trace_scores == [
        {
            "name": "turn_cache_hit_rate",
            "value": 0.5,
            "data_type": "NUMERIC",
            "comment": "cache_read=150, input=300",
        }
    ]
    assert tracing._turn_usage == {}


def test_nested_root_does_not_reclaim_or_finish_turn():
    outer = _FakeObservation()
    nested = _FakeObservation()  # sub-agent root: same trace, different run
    runs = {"outer": outer, "nested": nested}

    tracing._track_turn_start(runs, "outer")
    tracing._track_turn_start(runs, "nested")
    tracing._apply_cache_hit_rate(
        runs,
        "nested",
        _FakeLLMResult({"input_tokens": 10, "input_token_details": {"cache_read": 5}}),
    )

    # The nested root ends first; the turn must stay open for the outer owner.
    tracing._finish_turn(runs, "nested")
    assert nested.trace_scores == []
    assert tracing._turn_usage != {}

    tracing._finish_turn(runs, "outer")
    assert len(outer.trace_scores) == 1
    assert tracing._turn_usage == {}


def test_finish_turn_without_llm_calls_emits_no_score():
    root = _FakeObservation()
    runs = {"root": root}

    tracing._track_turn_start(runs, "root")
    tracing._finish_turn(runs, "root")

    assert root.trace_scores == []
    assert tracing._turn_usage == {}


def test_apply_cache_hit_rate_skips_zero_input():
    generation = _FakeObservation()

    tracing._apply_cache_hit_rate(
        {"llm": generation}, "llm", _FakeLLMResult({"input_tokens": 0})
    )

    assert generation.scores == []


def test_unclaimed_trace_accumulates_nothing():
    # Ad-hoc LLM calls outside a chain never claim their trace: they get the
    # generation score but must not leak accumulator entries.
    generation = _FakeObservation()

    tracing._apply_cache_hit_rate(
        {"llm": generation},
        "llm",
        _FakeLLMResult({"input_tokens": 10, "input_token_details": {"cache_read": 2}}),
    )

    assert len(generation.scores) == 1
    assert tracing._turn_usage == {}


class _FakeBaseHandler:
    """Stands in for langfuse.langchain.CallbackHandler in wiring tests."""

    def __init__(self):
        self._runs = {}
        self.calls: list[str] = []

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kw):
        # The real base creates the observation before our subclass hook runs.
        self._runs[run_id] = self._runs.get(run_id) or _FakeObservation()
        self.calls.append("chain_start")

    def on_llm_end(self, response, *, run_id, parent_run_id=None, **kw):
        self.calls.append("llm_end")

    def on_chain_end(self, outputs, *, run_id, parent_run_id=None, **kw):
        self.calls.append("chain_end")

    def on_chain_error(self, error, *, run_id, parent_run_id=None, **kw):
        self.calls.append("chain_error")


@pytest.mark.parametrize("root_callback", ["on_chain_end", "on_chain_error"])
def test_handler_wiring_scores_turn_on_root_end(root_callback):
    handler = tracing._build_cost_forwarding_handler(_FakeBaseHandler)
    handler.on_chain_start({}, {}, run_id="root")
    root = handler._runs["root"]
    generation = _FakeObservation()
    handler._runs["llm"] = generation

    handler.on_llm_end(
        _FakeLLMResult(
            {"input_tokens": 100, "input_token_details": {"cache_read": 25}}
        ),
        run_id="llm",
        parent_run_id="root",
    )
    # A non-root chain end must not close the turn.
    getattr(handler, root_callback)(object(), run_id="llm", parent_run_id="root")
    assert tracing._turn_usage != {}

    getattr(handler, root_callback)(object(), run_id="root")

    assert [s["name"] for s in generation.scores] == ["generation_cache_hit_rate"]
    assert [s["name"] for s in root.trace_scores] == ["turn_cache_hit_rate"]
    assert root.trace_scores[0]["value"] == 0.25
    assert tracing._turn_usage == {}
    # The base handler still received every callback.
    assert handler.calls == [
        "chain_start",
        "llm_end",
        root_callback.removeprefix("on_"),
        root_callback.removeprefix("on_"),
    ]


class _FakePropagate:
    entered: list[dict] = []
    exited: int = 0

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        _FakePropagate.entered.append(self.kwargs)
        return None

    def __exit__(self, *exc):
        _FakePropagate.exited += 1
        return False


def test_propagate_trace_attributes_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(tracing, "_hook_registered", False)
    _FakePropagate.entered = []
    monkeypatch.setattr("langfuse.propagate_attributes", _FakePropagate)

    with tracing.propagate_trace_attributes(session_id="s1", user_id="u1"):
        pass

    assert _FakePropagate.entered == []


def test_propagate_trace_attributes_wraps_run(monkeypatch):
    monkeypatch.setattr(tracing, "_hook_registered", True)
    _FakePropagate.entered = []
    _FakePropagate.exited = 0
    monkeypatch.setattr("langfuse.propagate_attributes", _FakePropagate)

    with tracing.propagate_trace_attributes(session_id="s1", user_id="u1"):
        assert _FakePropagate.entered == [{"session_id": "s1", "user_id": "u1"}]

    assert _FakePropagate.exited == 1


def test_propagate_trace_attributes_survives_enter_failure(monkeypatch):
    monkeypatch.setattr(tracing, "_hook_registered", True)

    class _Boom:
        def __init__(self, **kwargs):
            raise RuntimeError("no otel context")

    monkeypatch.setattr("langfuse.propagate_attributes", _Boom)

    ran = False
    with tracing.propagate_trace_attributes(session_id="s1"):
        ran = True
    assert ran


class _FakeClient:
    def __init__(self):
        self.scores: list[dict] = []

    def create_score(self, **kwargs):
        self.scores.append(kwargs)


def test_record_conversation_cache_hit_rate(monkeypatch):
    monkeypatch.setattr(tracing, "_hook_registered", True)
    client = _FakeClient()
    monkeypatch.setattr("langfuse.get_client", lambda: client)

    tracing.record_conversation_cache_hit_rate(
        session_id="agent-chat", input_tokens=1000, cached_tokens=250
    )

    assert client.scores == [
        {
            "name": "conversation_cache_hit_rate",
            "value": 0.25,
            "session_id": "agent-chat",
            "score_id": "conv-cache-hit-agent-chat",
            "data_type": "NUMERIC",
            "comment": "cache_read=250, input=1000",
        }
    ]


def test_record_conversation_cache_hit_rate_noop_cases(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr("langfuse.get_client", lambda: client)

    # Tracing disabled.
    monkeypatch.setattr(tracing, "_hook_registered", False)
    tracing.record_conversation_cache_hit_rate(
        session_id="s", input_tokens=100, cached_tokens=10
    )
    # No tokens spent yet.
    monkeypatch.setattr(tracing, "_hook_registered", True)
    tracing.record_conversation_cache_hit_rate(
        session_id="s", input_tokens=0, cached_tokens=0
    )

    assert client.scores == []


def test_setup_langfuse_runs_once_per_process(monkeypatch):
    registered = _reset(monkeypatch)

    _ = tracing.setup_langfuse(
        public_key="pk",
        secret_key="sk",
        base_url=None,
        environment="local",
        release=None,
    )
    _ = tracing.setup_langfuse(
        public_key="pk",
        secret_key="sk",
        base_url=None,
        environment="local",
        release=None,
    )

    # The second call is a no-op: the hook is registered once, and the client
    # and handler are never rebuilt (so background threads are not leaked).
    assert len(registered) == 1
    assert len(_FakeLangfuse.instances) == 1
    assert _FakeHandler.created == 1
