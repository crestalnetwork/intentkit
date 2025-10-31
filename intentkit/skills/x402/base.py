import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from coinbase_agentkit.wallet_providers.evm_wallet_provider import (
    EvmWalletSigner as CoinbaseEvmWalletSigner,
)
from x402.clients.httpx import x402HttpxClient

from intentkit.clients import get_wallet_provider
from intentkit.skills.onchain import IntentKitOnChainSkill

logger = logging.getLogger(__name__)


class X402BaseSkill(IntentKitOnChainSkill):
    """Base class for x402 skills."""

    @property
    def category(self) -> str:
        return "x402"

    async def _get_signer(self) -> "ThreadSafeEvmWalletSigner":
        context = self.get_context()
        wallet_provider = await get_wallet_provider(context.agent)
        return ThreadSafeEvmWalletSigner(wallet_provider)

    @asynccontextmanager
    async def http_client(
        self,
        timeout: float = 30.0,
    ) -> AsyncIterator[x402HttpxClient]:
        account = await self._get_signer()
        try:
            async with x402HttpxClient(
                account=account,
                timeout=timeout,
            ) as client:
                yield client
        except Exception:
            logger.exception("Failed to create x402 HTTP client")
            raise


class ThreadSafeEvmWalletSigner(CoinbaseEvmWalletSigner):
    """EVM wallet signer that avoids nested event loop errors.

    Coinbase's signer runs async wallet calls in the current thread. When invoked
    inside an active asyncio loop (as happens in async skills), it trips over the
    loop already running. We hop work to a background thread so the provider can
    spin up its own loop safely.
    """

    def __init__(self, wallet_provider: Any):
        super().__init__(wallet_provider=wallet_provider)

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
        domain_data: Any | None = None,
        message_types: Any | None = None,
        message_data: Any | None = None,
        full_message: Any | None = None,
    ) -> Any:
        return self._run_in_thread(
            super().sign_typed_data,
            domain_data=domain_data,
            message_types=message_types,
            message_data=message_data,
            full_message=full_message,
        )
