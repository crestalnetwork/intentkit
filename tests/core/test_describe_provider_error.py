"""Tests for describe_provider_error.

The engine's error log used to record only ``str(exc)``, which for SDK
errors like OpenRouter's is a terse message ("Provider returned error")
while the actual root cause — the upstream status code and the provider's
own error text in the response body — was lost. The helper must surface
both, walking wrapped exception chains the same way the retry predicate
does, and must never raise or break the single-line log format.
"""

import httpx
import httpx2
import openai
from openrouter.errors import OpenRouterError

from intentkit.utils.error import (
    _PROVIDER_ERROR_BODY_LIMIT,
    describe_provider_error,
)


def _response(status_code: int, body: str = "") -> httpx.Response:
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return httpx.Response(status_code, request=request, text=body)


class TestDescribeProviderError:
    def test_openrouter_error_includes_status_and_body(self):
        body = '{"error":{"code":400,"message":"Provider returned error","metadata":{"raw":"deepseek: invalid request"}}}'
        exc = OpenRouterError(
            "Provider returned error", _response(400, body), body=body
        )
        detail = describe_provider_error(exc)
        assert "type=OpenRouterError" in detail
        assert "status=400" in detail
        assert "deepseek: invalid request" in detail

    def test_openai_stream_error_uses_code_and_body(self):
        # Mid-stream SSE errors surface as openai.APIError: no status_code
        # attribute, only `code` lifted from the error body.
        body = {"code": 502, "message": "Provider returned error"}
        exc = openai.APIError(
            "Provider returned error",
            httpx2.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
            body=body,
        )
        detail = describe_provider_error(exc)
        assert "status=502" in detail
        assert "Provider returned error" in detail

    def test_non_numeric_code_is_not_labeled_status(self):
        exc = openai.APIError(
            "quota exceeded",
            httpx2.Request("POST", "https://api.openai.com/v1/chat/completions"),
            body={"code": "insufficient_quota"},
        )
        detail = describe_provider_error(exc)
        assert "code=insufficient_quota" in detail
        assert "status=" not in detail

    def test_digit_string_status_is_coerced(self):
        class FakeError(Exception):
            code = "502"

        assert "status=502" in describe_provider_error(FakeError("x"))

    def test_httpx_error_falls_back_to_response_text(self):
        # httpx-style wrappers have no .body; the payload lives on .response.
        resp = _response(503, "upstream unavailable")
        exc = httpx.HTTPStatusError("server error", request=resp.request, response=resp)
        detail = describe_provider_error(exc)
        assert "status=503" in detail
        assert "body=upstream unavailable" in detail

    def test_empty_body_omits_body_field(self):
        exc = OpenRouterError("Provider returned error", _response(502), body="")
        detail = describe_provider_error(exc)
        assert "status=502" in detail
        assert "body=" not in detail

    def test_newlines_in_body_are_escaped(self):
        body = "line1\nline2\r\nline3"
        exc = OpenRouterError("err", _response(502, body), body=body)
        detail = describe_provider_error(exc)
        assert "\n" not in detail
        assert "\r" not in detail
        assert "line1\\nline2\\r\\nline3" in detail

    def test_wrapped_cause_chain_is_walked(self):
        inner = OpenRouterError("Provider returned error", _response(400, "{}"))
        outer = RuntimeError("agent execution failed")
        outer.__cause__ = inner
        assert "status=400" in describe_provider_error(outer)

    def test_implicit_context_chain_is_walked(self):
        try:
            try:
                raise OpenRouterError("Provider returned error", _response(502, "{}"))
            except OpenRouterError:
                raise RuntimeError("wrapper")
        except RuntimeError as outer:
            assert "status=502" in describe_provider_error(outer)

    def test_deepest_detail_wins_over_wrapper_code(self):
        # A wrapper with a generic non-HTTP `code` must not mask the real
        # provider response buried deeper in the chain.
        class WrapperError(Exception):
            code = "AGENT_FAILED"

        outer = WrapperError("wrapped")
        outer.__cause__ = OpenRouterError(
            "Provider returned error", _response(502, "upstream died")
        )
        detail = describe_provider_error(outer)
        assert "status=502" in detail
        assert "AGENT_FAILED" not in detail

    def test_plain_exception_yields_empty_string(self):
        assert describe_provider_error(ValueError("boom")) == ""

    def test_body_is_truncated_with_marker(self):
        body = "x" * (_PROVIDER_ERROR_BODY_LIMIT * 3)
        exc = OpenRouterError("err", _response(502, body), body=body)
        detail = describe_provider_error(exc)
        assert detail.endswith("...(truncated)")
        assert len(detail) < _PROVIDER_ERROR_BODY_LIMIT + 200

    def test_formatting_failure_degrades_to_empty_string(self):
        class Unprintable:
            def __str__(self) -> str:
                raise RuntimeError("no repr for you")

        class FakeError(Exception):
            status_code = 500
            body = Unprintable()

        assert describe_provider_error(FakeError("x")) == ""

    def test_circular_cause_chain_terminates(self):
        a = ValueError("a")
        b = ValueError("b")
        a.__cause__ = b
        b.__cause__ = a
        assert describe_provider_error(a) == ""
