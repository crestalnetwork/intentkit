"""Tests for the startup readiness wait helpers."""

import pytest

from intentkit.utils.readiness import wait_until_ready, wait_until_ready_sync


class Flaky:
    """Probe that fails ``failures`` times before succeeding."""

    def __init__(self, failures: int, exc: Exception):
        self.failures = failures
        self.exc = exc
        self.calls = 0

    def probe_sync(self) -> None:
        self.calls += 1
        if self.calls <= self.failures:
            raise self.exc

    async def probe(self) -> None:
        self.probe_sync()


async def _wait(variant: str, flaky: Flaky, **kwargs: float) -> None:
    """Run the async or sync helper against the flaky probe."""
    if variant == "async":
        await wait_until_ready("dep", flaky.probe, (ConnectionError,), **kwargs)
    else:
        wait_until_ready_sync("dep", flaky.probe_sync, (ConnectionError,), **kwargs)


VARIANTS = ["async", "sync"]


@pytest.mark.asyncio
@pytest.mark.parametrize("variant", VARIANTS)
async def test_returns_immediately_on_success(variant):
    flaky = Flaky(failures=0, exc=ConnectionError())
    await _wait(variant, flaky, timeout=1)
    assert flaky.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("variant", VARIANTS)
async def test_retries_retryable_until_success(variant):
    flaky = Flaky(failures=2, exc=ConnectionError("booting"))
    await _wait(variant, flaky, timeout=1, interval=0.001)
    assert flaky.calls == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("variant", VARIANTS)
async def test_non_retryable_propagates_immediately(variant):
    flaky = Flaky(failures=5, exc=ValueError("bad config"))
    with pytest.raises(ValueError, match="bad config"):
        await _wait(variant, flaky, timeout=1, interval=0.001)
    assert flaky.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("variant", VARIANTS)
async def test_raises_last_error_when_deadline_expires(variant):
    flaky = Flaky(failures=100, exc=ConnectionError("still down"))
    # The next retry would land past the deadline, so it gives up on the
    # first failure without sleeping.
    with pytest.raises(ConnectionError, match="still down"):
        await _wait(variant, flaky, timeout=0.01, interval=1)
    assert flaky.calls == 1
