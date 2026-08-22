"""Tests for the executor's retry predicates.

``_should_retry_model_failure`` feeds ModelRetryMiddleware and must retry
only transient API failures: permanent errors have to propagate so the
engine's error handling (system error messages, checkpoint cleanup) still
runs instead of the failure being retried pointlessly.
"""

import httpcore
import httpcore2
import httpx
import httpx2
import openai
import pytest
from anthropic import APIStatusError as AnthropicAPIStatusError
from langchain_core.exceptions import (
    ContextOverflowError,
    ModelAPIError,
    ModelAuthenticationError,
    ModelConnectionError,
    ModelInvalidRequestError,
    ModelNotFoundError,
    ModelRateLimitError,
    ModelTimeoutError,
)
from langchain_core.tools.base import ToolException
from langchain_google_genai.chat_models import GoogleRateLimitError
from openrouter.errors import OpenRouterError, ResponseValidationError
from pydantic import BaseModel, ValidationError

from intentkit.core.executor import (
    _should_retry_model_failure,
    _should_retry_tool_failure,
)
from intentkit.utils.error import http_status_candidates


def _response(status_code: int) -> httpx.Response:
    request = httpx.Request("POST", "https://api.example.com/v1/messages")
    return httpx.Response(status_code, request=request)


def _response2(status_code: int) -> httpx2.Response:
    """httpx2 twin of ``_response`` — openai 3.x errors carry httpx2 objects."""
    request = httpx2.Request("POST", "https://api.example.com/v1/messages")
    return httpx2.Response(status_code, request=request)


def _response_validation_error(
    cause: Exception, status_code: int = 200
) -> ResponseValidationError:
    """Build the error the openrouter SDK raises when a body won't unmarshal.

    Raised via ``from cause`` to mirror unmarshal_json_response: the SDK's
    constructor does not set ``__cause__`` itself, the raise statement does,
    and ``__cause__`` is what tells a truncated body from a schema mismatch.
    """
    try:
        raise ResponseValidationError(
            "Response validation failed", _response(status_code), cause
        ) from cause
    except ResponseValidationError as exc:
        return exc


def _schema_mismatch() -> ValidationError:
    """A body that parsed as JSON but did not match the SDK's model."""

    class Body(BaseModel):
        id: str

    with pytest.raises(ValidationError) as exc_info:
        Body(id=123)  # pyright: ignore[reportArgumentType]
    return exc_info.value


class TestShouldRetryModelFailure:
    def test_connection_and_timeout_errors_retry(self):
        assert _should_retry_model_failure(ConnectionError("reset"))
        assert _should_retry_model_failure(TimeoutError("timed out"))

    # openai 3.x runs on httpx2/httpcore2, everything else on httpx/httpcore —
    # transport errors from either stack must retry identically.
    @pytest.mark.parametrize(
        ("http_mod", "core_mod"),
        [(httpx, httpcore), (httpx2, httpcore2)],
        ids=["httpx", "httpx2"],
    )
    def test_transport_errors_retry(self, http_mod, core_mod):
        assert _should_retry_model_failure(http_mod.ConnectError("refused"))
        # Mid-stream disconnect — the case SDK-level retries never cover.
        assert _should_retry_model_failure(
            http_mod.RemoteProtocolError("peer closed connection")
        )
        # Raw httpcore errors leak past httpx wrapping in practice.
        assert _should_retry_model_failure(core_mod.ReadTimeout("read timeout"))
        assert _should_retry_model_failure(core_mod.ConnectError("refused"))
        assert _should_retry_model_failure(
            core_mod.RemoteProtocolError("peer closed connection")
        )

    def test_openai_transient_statuses_retry(self):
        rate_limited = openai.RateLimitError(
            "rate limited", response=_response2(429), body=None
        )
        assert _should_retry_model_failure(rate_limited)
        server_error = openai.InternalServerError(
            "server error", response=_response2(500), body=None
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
            f"status {status}", response=_response2(status), body=None
        )
        assert _should_retry_model_failure(exc)

    def test_permanent_statuses_do_not_retry(self):
        for status in (400, 401, 403, 404, 422):
            exc = openai.APIStatusError(
                f"status {status}", response=_response2(status), body=None
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
            request=httpx2.Request("POST", "https://api.example.com")
        )
        wrapper.__cause__ = httpx2.ConnectError("refused")
        assert _should_retry_model_failure(wrapper)

    @pytest.mark.parametrize("http_mod", [httpx, httpx2], ids=["httpx", "httpx2"])
    def test_implicit_context_chain_is_walked(self, http_mod):
        # `raise Y` inside an except block sets __context__, not __cause__.
        with pytest.raises(RuntimeError) as exc_info:
            try:
                raise http_mod.ConnectError("refused")
            except http_mod.ConnectError:
                raise RuntimeError("wrapped without from")
        assert _should_retry_model_failure(exc_info.value)

    @pytest.mark.parametrize("http_mod", [httpx, httpx2], ids=["httpx", "httpx2"])
    def test_suppressed_context_is_not_walked(self, http_mod):
        # `raise Y from None` explicitly severs the chain.
        with pytest.raises(RuntimeError) as exc_info:
            try:
                raise http_mod.ConnectError("refused")
            except http_mod.ConnectError:
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


class TestStandardModelExceptions:
    """langchain-core 1.6 gave integrations a shared exception vocabulary.

    ``ModelError.is_retryable`` is set by the provider from the condition it
    actually saw, so it beats the status duck-typing — and it is the only
    signal for integrations that drop the status on the floor.
    """

    @pytest.mark.parametrize(
        "exc",
        [
            ModelRateLimitError("rate limited"),
            ModelAPIError("provider 5xx"),
            ModelConnectionError("provider unreachable"),
            ModelTimeoutError("timed out"),
        ],
        ids=["rate-limit", "api", "connection", "timeout"],
    )
    def test_retryable_model_errors_retry(self, exc: Exception):
        # Integrations raise subclasses that also inherit the SDK's own error
        # (OpenAIRateLimitError is an openai.RateLimitError), so putting this
        # branch first changes which check answers, never the answer.
        assert _should_retry_model_failure(exc)

    @pytest.mark.parametrize(
        "exc",
        [
            ModelAuthenticationError("bad key"),
            ModelInvalidRequestError("malformed request"),
            ModelNotFoundError("no such model"),
            ContextOverflowError("input exceeds the context window"),
        ],
        ids=["auth", "invalid-request", "not-found", "context-overflow"],
    )
    def test_permanent_model_errors_do_not_retry(self, exc: Exception):
        assert not _should_retry_model_failure(exc)

    def test_google_rate_limit_retries_without_any_status(self):
        # GoogleRateLimitError carries no status_code, code, or response at
        # all — before the standard vocabulary the 429 survived only if the
        # raw ClientError happened to still be on the chain.
        exc = GoogleRateLimitError("Error calling model 'gemini': quota exceeded")
        assert not any(http_status_candidates(exc))
        assert _should_retry_model_failure(exc)

    def test_permanent_condition_beats_a_retryable_status(self):
        # langchain-openai raises OpenAIAPIContextOverflowError off a generic
        # openai.APIError, which can carry a 5xx-shaped status. Retrying it
        # burns every attempt on input that will never fit.
        class ServerShapedOverflow(ContextOverflowError):
            status_code = 503

        assert not _should_retry_model_failure(
            ServerShapedOverflow("exceeds the context window")
        )

    def test_transport_cause_under_a_permanent_model_error_does_not_retry(self):
        # The outermost classified verdict wins: a provider that calls the
        # request invalid means it, whatever noise is further down the chain.
        exc = ModelInvalidRequestError("malformed request")
        exc.__cause__ = httpx.ConnectError("refused")
        assert not _should_retry_model_failure(exc)

    def test_model_error_on_the_cause_is_still_found(self):
        wrapper = RuntimeError("model call failed")
        wrapper.__cause__ = ModelRateLimitError("rate limited")
        assert _should_retry_model_failure(wrapper)


class TestOpenRouterResponseFailures:
    """OpenRouter SDK failures that need care beyond the plain status filter.

    A body truncated mid-stream arrives as a would-be-permanent parse failure
    on a 2xx and must be retried, while the same parse failure on a 4xx, a real
    schema mismatch, or a spent key must stay final.
    """

    def test_truncated_body_retries(self):
        # HTTP 200 whose JSON stopped mid-value: pydantic_core.from_json raises
        # a bare ValueError, which the SDK wraps as ResponseValidationError.
        exc = _response_validation_error(
            ValueError("EOF while parsing a value at line 175 column 0")
        )
        assert _should_retry_model_failure(exc)

    @pytest.mark.parametrize("status_code", [400, 402, 404, 422])
    def test_truncated_body_on_permanent_status_does_not_retry(self, status_code: int):
        # The SDK unmarshals error bodies too, so a 4xx whose body is truncated
        # or non-JSON (a gateway's HTML page) also arrives as a
        # ResponseValidationError. Its status is the honest signal: a truncated
        # 402 "Key limit exceeded" is exactly as final as an intact one.
        exc = _response_validation_error(
            ValueError("EOF while parsing a value at line 1 column 0"),
            status_code=status_code,
        )
        assert not _should_retry_model_failure(exc)

    @pytest.mark.parametrize(
        ("status_code", "retries"),
        [
            # Schema drift on a good response is SDK/API drift — permanent, and
            # retrying would burn three attempts on every request until noticed.
            (200, False),
            # ...but drift on a 503 is incidental; the status filter must win.
            (503, True),
        ],
    )
    def test_schema_mismatch_retries_only_on_transient_status(
        self, status_code: int, retries: bool
    ):
        exc = _response_validation_error(_schema_mismatch(), status_code=status_code)
        assert _should_retry_model_failure(exc) is retries

    def test_unrelated_openrouter_4xx_does_not_retry(self):
        exc = OpenRouterError(
            "No endpoints found matching your data policy", _response(404)
        )
        assert not _should_retry_model_failure(exc)

    def test_openrouter_transient_statuses_retry(self):
        # A plain OpenRouterError is retried purely on its status: rate limits
        # and provider outages go through the same duck-typed filter.
        assert _should_retry_model_failure(
            OpenRouterError("Rate limit exceeded", _response(429))
        )
        assert _should_retry_model_failure(
            OpenRouterError("Provider overloaded", _response(503))
        )

    def test_key_limit_exceeded_does_not_retry(self):
        # A spent key is permanent until a human resets it; retrying only
        # delays the error the operator needs to see.
        exc = OpenRouterError("Key limit exceeded (monthly limit).", _response(402))
        assert not _should_retry_model_failure(exc)


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
