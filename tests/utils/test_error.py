import anthropic
import httpcore
import httpcore2
import httpx
import httpx2
import openai
import pytest
from langchain_core.exceptions import ModelTimeoutError

from intentkit.utils.error import (
    TRANSPORT_TIMEOUT_ERRORS,
    format_validation_errors,
)


class TestTransportTimeoutErrors:
    """The tuple feeds plain ``except`` clauses (core/engine/stream.py), which
    never walk ``__cause__`` — so both raw transport timeouts from either HTTP
    stack and the SDK timeout wrappers must match directly."""

    @pytest.mark.parametrize(
        "exc",
        [
            TimeoutError("timed out"),
            httpx.ReadTimeout("read timeout"),
            httpx2.ReadTimeout("read timeout"),
            httpcore.PoolTimeout("pool timeout"),
            httpcore2.ConnectTimeout("connect timeout"),
            openai.APITimeoutError(
                request=httpx2.Request("POST", "https://api.example.com")
            ),
            anthropic.APITimeoutError(
                request=httpx.Request("POST", "https://api.example.com")
            ),
            ModelTimeoutError("model request timed out"),
        ],
        ids=[
            "builtin",
            "httpx-read",
            "httpx2-read",
            "httpcore-pool",
            "httpcore2-connect",
            "openai-wrapper",
            "anthropic-wrapper",
            "langchain-standard",
        ],
    )
    def test_timeouts_classify_as_timeout(self, exc: Exception):
        with pytest.raises(TRANSPORT_TIMEOUT_ERRORS):
            raise exc


def test_format_validation_errors_with_field_path_and_type():
    errors = [
        {
            "loc": ("body", "user", "email"),
            "msg": "value is not a valid email address",
            "type": "value_error.email",
        },
        {
            "loc": ("body", "items", 0, "price"),
            "msg": "value is not a valid decimal",
            "type": "type_error.decimal",
        },
    ]

    result = format_validation_errors(errors)

    assert (
        "Field 'user -> email' (value_error.email): value is not a valid email address"
        in result
    )
    assert (
        "Field 'items -> 0 -> price' (type_error.decimal): value is not a valid decimal"
        in result
    )


def test_format_validation_errors_without_field_path():
    errors = [
        {
            "loc": (),
            "msg": "root error",
            "type": "value_error",
        }
    ]

    assert format_validation_errors(errors) == "root error"
