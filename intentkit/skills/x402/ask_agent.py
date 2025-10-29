import threading
from typing import Any, Dict, Optional, Type

from coinbase_agentkit.wallet_providers.evm_wallet_provider import (
    EvmWalletSigner as CoinbaseEvmWalletSigner,
)
from langchain_core.tools import ToolException
from pydantic import BaseModel, Field
from x402.clients.httpx import x402HttpxClient

from intentkit.clients import get_wallet_provider
from intentkit.config.config import config
from intentkit.models.chat import AuthorType
from intentkit.skills.x402.base import X402BaseSkill


class AskAgentInput(BaseModel):
    """Arguments for the x402 ask agent skill."""

    agent_id: str = Field(description="ID or slug of the agent to query.")
    message: str = Field(description="Message to send to the target agent.")
    search_mode: Optional[bool] = Field(
        default=None, description="Enable search mode when interacting with the agent."
    )
    super_mode: Optional[bool] = Field(
        default=None, description="Enable super mode when interacting with the agent."
    )


class X402AskAgent(X402BaseSkill):
    """Skill that queries another agent via the x402 API."""

    name: str = "x402_ask_agent"
    description: str = (
        "Call another agent through the x402 API and return the final agent message."
    )
    args_schema: Type[BaseModel] = AskAgentInput

    async def _arun(
        self,
        agent_id: str,
        message: str,
        search_mode: Optional[bool] = None,
        super_mode: Optional[bool] = None,
    ) -> str:
        base_url = (config.open_api_base_url or "").rstrip("/")
        if not base_url:
            raise ValueError("X402 API base URL is not configured.")

        # Use wallet provider signer to satisfy eth_account.BaseAccount interface requirements
        context = self.get_context()
        wallet_provider = await get_wallet_provider(context.agent)
        account = ThreadSafeEvmWalletSigner(wallet_provider)

        payload: Dict[str, Any] = {
            "agent_id": agent_id,
            "message": message,
            "app_id": "skill",
        }
        if search_mode is not None:
            payload["search_mode"] = search_mode
        if super_mode is not None:
            payload["super_mode"] = super_mode

        async with x402HttpxClient(
            account=account,
            base_url=base_url,
            timeout=20.0,
        ) as client:
            response = await client.post("/x402", json=payload)
            response.raise_for_status()
            messages = response.json()
        if not isinstance(messages, list) or not messages:
            raise ValueError("Agent returned an empty response.")

        last_message = messages[-1]
        if not isinstance(last_message, dict):
            raise ValueError("Agent response format is invalid.")

        author_type = last_message.get("author_type")
        content = last_message.get("message")

        if author_type == AuthorType.SYSTEM.value:
            raise ToolException(content or "Agent returned a system message.")

        if not content:
            raise ToolException("Agent response did not include message text.")

        return str(content)


class ThreadSafeEvmWalletSigner(CoinbaseEvmWalletSigner):
    """EVM wallet signer that avoids nested event loop errors.

    Coinbase's signer runs async wallet calls in the current thread. When invoked
    inside an active asyncio loop (as happens in async skills), it trips over the
    loop already running. We hop work to a background thread so the provider can
    spin up its own loop safely.
    """

    def _run_in_thread(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        result: list[Any] = []
        error: list[BaseException] = []

        def _target() -> None:
            try:
                result.append(func(*args, **kwargs))
            except BaseException as exc:  # pragma: no cover - bubble up original error
                error.append(exc)

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join()

        if error:
            raise error[0]
        return result[0] if result else None

    def unsafe_sign_hash(self, message_hash: Any) -> Any:
        return self._run_in_thread(super().unsafe_sign_hash, message_hash)

    def sign_message(self, signable_message: Any) -> Any:
        return self._run_in_thread(super().sign_message, signable_message)

    def sign_transaction(self, transaction_dict: Any) -> Any:
        return self._run_in_thread(super().sign_transaction, transaction_dict)

    def sign_typed_data(
        self,
        domain_data: Optional[Dict[str, Any]] = None,
        message_types: Optional[Dict[str, Any]] = None,
        message_data: Optional[Dict[str, Any]] = None,
        full_message: Optional[Dict[str, Any]] = None,
    ) -> Any:
        return self._run_in_thread(
            super().sign_typed_data,
            domain_data=domain_data,
            message_types=message_types,
            message_data=message_data,
            full_message=full_message,
        )
