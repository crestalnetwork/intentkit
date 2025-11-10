"""Utilities for resolving ENS domains to wallet addresses."""

from __future__ import annotations

import asyncio
import logging

from ens import ENS
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from intentkit.config.config import config
from intentkit.models.redis import get_redis
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "intentkit:ens:"
_CACHE_TTL_SECONDS = 4 * 60 * 60

_NETWORKS_BY_SUFFIX: dict[str, tuple[str, ...]] = {
    ".base.eth": ("base-mainnet", "ethereum-mainnet"),
    ".eth": ("ethereum-mainnet",),
}

_POA_NETWORK_PREFIXES: tuple[str, ...] = ("base",)


async def resolve_ens_to_address(name: str) -> str:
    """Resolve an ENS domain to a checksum wallet address.

    Args:
        name: ENS name to resolve.

    Returns:
        The checksum wallet address associated with the ENS name.

    Raises:
        IntentKitAPIError: If the ENS name cannot be resolved to a wallet address.
    """

    normalized = name.strip().lower()
    if not normalized:
        raise IntentKitAPIError(404, "ENSNameNotFound", "ENS name is empty.")

    redis_client = None
    cache_key = f"{_CACHE_PREFIX}{normalized}"
    try:
        redis_client = get_redis()
    except Exception:  # Redis is optional; ignore if unavailable
        redis_client = None

    if redis_client is not None:
        cached_address = await redis_client.get(cache_key)
        if cached_address:
            return cached_address

    networks = _networks_for_name(normalized)
    if not networks:
        raise IntentKitAPIError(
            404,
            "ENSNameNotFound",
            "Unsupported ENS name suffix.",
        )

    for network in networks:
        address = await _resolve_on_network(normalized, network)
        if address:
            if redis_client is not None:
                try:
                    await redis_client.set(cache_key, address, ex=_CACHE_TTL_SECONDS)
                except Exception as exc:  # pragma: no cover - optional cache
                    logger.debug("Failed to cache ENS resolution: %s", exc)
            return address

    raise IntentKitAPIError(
        404,
        "ENSNameNotFound",
        f"ENS name {name} could not be resolved.",
    )


def _networks_for_name(name: str) -> tuple[str, ...]:
    for suffix, networks in _NETWORKS_BY_SUFFIX.items():
        if name.endswith(suffix):
            return networks
    return tuple()


def _requires_poa_middleware(network: str) -> bool:
    return network.startswith(_POA_NETWORK_PREFIXES)


def _build_ens_client(rpc_url: str, network: str) -> ENS:
    web3_client = Web3(Web3.HTTPProvider(rpc_url))
    if _requires_poa_middleware(network):
        web3_client.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    return ENS.from_web3(web3_client)


async def _resolve_on_network(name: str, network: str) -> str | None:
    chain_provider = getattr(config, "chain_provider", None)
    if chain_provider is None:
        logger.debug("No chain provider configured; cannot resolve ENS name.")
        return None

    try:
        chain_config = chain_provider.get_chain_config(network)
    except Exception as exc:  # pragma: no cover - dependent on external config
        logger.debug("Chain config for %s unavailable: %s", network, exc)
        return None

    rpc_url = chain_config.ens_url or chain_config.rpc_url
    if not rpc_url:
        logger.debug("No RPC/ENS URL configured for %s", network)
        return None

    def _resolve() -> str | None:
        ens_client = _build_ens_client(rpc_url, network)
        try:
            resolved = ens_client.address(name)
        except Exception as exc:  # pragma: no cover - dependent on external provider
            logger.debug("Error resolving %s on %s: %s", name, network, exc)
            return None

        if not resolved:
            return None

        try:
            return Web3.to_checksum_address(resolved)
        except ValueError:
            return None

    return await asyncio.to_thread(_resolve)
