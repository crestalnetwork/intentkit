"""Shared constructor for the OpenRouter SDK client.

Attribution headers identify IntentKit in OpenRouter's app rankings, so every
call site has to send the same ones — this is the single place that knows
them. Callers that need a bounded retry budget pass ``retry_config``; see
``bounded_retry_config`` for why the SDK default is not always suitable.
"""

import openrouter
from openrouter.utils.retries import BackoffStrategy, RetryConfig

from intentkit.config.config import config

# Attribution, as registered with OpenRouter.
_APP_URL = "https://github.com/crestalnetwork/intentkit"
_APP_TITLE = "IntentKit"
_APP_CATEGORIES = "cloud-agent"


def get_openrouter_client(
    *,
    timeout_ms: int = 120_000,
    retry_config: RetryConfig | None = None,
) -> openrouter.OpenRouter:
    """Build an OpenRouter client with IntentKit's attribution headers.

    Raises ``ValueError`` when no API key is configured; callers in tool code
    translate that into a ``ToolException``.
    """
    key = config.openrouter_api_key
    if not key:
        raise ValueError("OpenRouter API key is not configured")
    return openrouter.OpenRouter(
        api_key=key,
        http_referer=_APP_URL,
        x_open_router_title=_APP_TITLE,
        x_open_router_categories=_APP_CATEGORIES,
        timeout_ms=timeout_ms,
        retry_config=retry_config,
    )


def bounded_retry_config(max_elapsed_ms: int = 30_000) -> RetryConfig:
    """A retry budget that cannot outlive an interactive agent turn.

    The SDK's default backoff allows ``max_elapsed_time`` of one hour per
    call. That is unusable where one logical operation makes many HTTP calls
    (video generation polls up to 60 times): a flapping upstream could pin a
    single request far past the operation's own deadline.
    """
    return RetryConfig(
        "backoff",
        BackoffStrategy(
            initial_interval=500,
            max_interval=5_000,
            exponent=1.5,
            max_elapsed_time=max_elapsed_ms,
        ),
        True,
    )
