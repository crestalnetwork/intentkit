"""Tests for the executor's retry predicates.

``_should_retry_model_failure`` feeds ModelRetryMiddleware and must retry
only transient API failures: permanent errors have to propagate so the
engine's error handling (system error messages, checkpoint cleanup) still
runs instead of the failure being retried pointlessly.
"""

import httpcore
import httpx
import openai
import pytest
from anthropic import APIStatusError as AnthropicAPIStatusError
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, ValidationError

from intentkit.core.executor import (
    _should_retry_model_failure,
    _should_retry_tool_failure,
)


def _response(status_code: int) -> httpx.Response:
    request = httpx.Request("POST", "https://api.example.com/v1/messages")
    return httpx.Response(status_code, request=request)


class TestShouldRetryModelFailure:
    def test_connection_and_timeout_errors_retry(self):
        assert _should_retry_model_failure(ConnectionError("reset"))
        assert _should_retry_model_failure(TimeoutError("timed out"))
        assert _should_retry_model_failure(httpx.ConnectError("refused"))
        # Mid-stream disconnect — the case SDK-level retries never cover.
        assert _should_retry_model_failure(
            httpx.RemoteProtocolError("peer closed connection")
        )
        assert _should_retry_model_failure(httpcore.ReadTimeout("read timeout"))
        # Raw httpcore errors leak past httpx wrapping in practice.
        assert _should_retry_model_failure(httpcore.ConnectError("refused"))
        assert _should_retry_model_failure(
            httpcore.RemoteProtocolError("peer closed connection")
        )

    def test_openai_transient_statuses_retry(self):
        rate_limited = openai.RateLimitError(
            "rate limited", response=_response(429), body=None
        )
        assert _should_retry_model_failure(rate_limited)
        server_error = openai.InternalServerError(
            "server error", response=_response(500), body=None
        )
        assert _should_retry_model_failure(server_error)

    def test_anthropic_overloaded_retries(self):
        overloaded = AnthropicAPIStatusError(
            "overloaded", response=_response(529), body=None
        )
        assert _should_retry_model_failure(overloaded)

    @pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504, 529])
    def test_transient_status_codes_retry(self, status: int):
        exc = openai.APIStatusError(
            f"status {status}", response=_response(status), body=None
        )
        assert _should_retry_model_failure(exc)

    def test_permanent_statuses_do_not_retry(self):
        for status in (400, 401, 403, 404, 422):
            exc = openai.APIStatusError(
                f"status {status}", response=_response(status), body=None
            )
            assert not _should_retry_model_failure(exc), status

    def test_wrapped_status_code_found_on_cause(self):
        # langchain-google-genai wraps 4xx ClientError (429 included) into a
        # ChatGoogleGenerativeAIError; the code only survives on __cause__.
        class FakeGoogleClientError(Exception):
            code = 429

        wrapper = RuntimeError("Error calling model 'gemini' (429): quota")
        wrapper.__cause__ = FakeGoogleClientError("quota exceeded")
        assert _should_retry_model_failure(wrapper)

    def test_wrapped_connection_error_found_on_cause(self):
        # openai/anthropic APIConnectionError carries the httpx error as cause.
        wrapper = openai.APIConnectionError(
            request=httpx.Request("POST", "https://api.example.com")
        )
        wrapper.__cause__ = httpx.ConnectError("refused")
        assert _should_retry_model_failure(wrapper)

    def test_implicit_context_chain_is_walked(self):
        # `raise Y` inside an except block sets __context__, not __cause__.
        with pytest.raises(RuntimeError) as exc_info:
            try:
                raise httpx.ConnectError("refused")
            except httpx.ConnectError:
                raise RuntimeError("wrapped without from")  # noqa: B904
        assert _should_retry_model_failure(exc_info.value)

    def test_suppressed_context_is_not_walked(self):
        # `raise Y from None` explicitly severs the chain.
        with pytest.raises(RuntimeError) as exc_info:
            try:
                raise httpx.ConnectError("refused")
            except httpx.ConnectError:
                raise RuntimeError("wrapped from None") from None
        assert not _should_retry_model_failure(exc_info.value)

    def test_string_status_codes_are_coerced(self):
        class FakeApiError(Exception):
            def __init__(self, code: str):
                super().__init__(code)
                self.code = code

        assert _should_retry_model_failure(FakeApiError("429"))
        assert _should_retry_model_failure(FakeApiError("503"))
        assert not _should_retry_model_failure(FakeApiError("400"))
        assert not _should_retry_model_failure(FakeApiError("RESOURCE_EXHAUSTED"))

    def test_status_code_found_on_response_attribute(self):
        exc = httpx.HTTPStatusError(
            "server error",
            request=httpx.Request("POST", "https://api.example.com"),
            response=_response(503),
        )
        assert _should_retry_model_failure(exc)

    def test_plain_exceptions_do_not_retry(self):
        assert not _should_retry_model_failure(ValueError("bad input"))
        assert not _should_retry_model_failure(RuntimeError("boom"))

    def test_circular_cause_chain_terminates(self):
        a = RuntimeError("a")
        b = RuntimeError("b")
        a.__cause__ = b
        b.__cause__ = a
        assert not _should_retry_model_failure(a)


class TestShouldRetryToolFailure:
    def test_transient_failures_retry(self):
        assert _should_retry_tool_failure(ConnectionError("reset"))
        assert _should_retry_tool_failure(RuntimeError("flaky backend"))

    def test_user_facing_errors_do_not_retry(self):
        assert not _should_retry_tool_failure(ToolException("insufficient balance"))

        class Args(BaseModel):
            amount: int

        with pytest.raises(ValidationError) as exc_info:
            Args(amount="not a number")  # pyright: ignore[reportArgumentType]
        assert not _should_retry_tool_failure(exc_info.value)
