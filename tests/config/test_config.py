from intentkit.config.config import Config, config

_LANGFUSE_ENV_VARS = (
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASE_URL",
    "LANGFUSE_HOST",
)


def _clear_tracing_env(monkeypatch):
    for var in _LANGFUSE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_load_strips_matching_surrounding_quotes(monkeypatch):
    monkeypatch.setenv("QUOTE_TEST_KEY", '"intentkit"')
    assert config.load("QUOTE_TEST_KEY") == "intentkit"

    monkeypatch.setenv("QUOTE_TEST_KEY", "'intentkit'")
    assert config.load("QUOTE_TEST_KEY") == "intentkit"

    monkeypatch.setenv("QUOTE_TEST_KEY", "plain")
    assert config.load("QUOTE_TEST_KEY") == "plain"

    # Mismatched quotes are kept as-is
    monkeypatch.setenv("QUOTE_TEST_KEY", "\"mismatched'")
    assert config.load("QUOTE_TEST_KEY") == "\"mismatched'"


def test_langfuse_enabled_with_both_keys(monkeypatch):
    _clear_tracing_env(monkeypatch)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    # Avoid initializing the real Langfuse client / global hook during the test.
    called = {}
    monkeypatch.setattr(
        Config, "_setup_langfuse", lambda self: called.setdefault("ran", True)
    )

    cfg = Config()

    assert cfg.langfuse_tracing is True
    assert called.get("ran") is True


def test_langfuse_disabled_without_both_keys(monkeypatch):
    _clear_tracing_env(monkeypatch)
    # Only the public key is present — not enough to enable Langfuse.
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setattr(Config, "_setup_langfuse", lambda self: None)

    cfg = Config()

    assert cfg.langfuse_tracing is False
