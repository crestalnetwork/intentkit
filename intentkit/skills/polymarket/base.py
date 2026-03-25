"""Base class for Polymarket prediction market skills."""

import base64
import hashlib
import hmac
import json
import logging
import math
import os
import time
from typing import Any

import httpx
from langchain_core.tools.base import ToolException

from intentkit.skills.onchain import IntentKitOnChainSkill

logger = logging.getLogger(__name__)

# API base URLs
GAMMA_URL = "https://gamma-api.polymarket.com"
CLOB_URL = "https://clob.polymarket.com"
DATA_URL = "https://data-api.polymarket.com"

# Polygon mainnet chain ID
CHAIN_ID = 137

# Contract addresses (Polygon mainnet)
EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_EXCHANGE_ADDRESS = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
COLLATERAL_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CONDITIONAL_TOKENS_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

# Signature types
SIG_EOA = 0
SIG_POLY_PROXY = 1
SIG_POLY_GNOSIS_SAFE = 2

# Order sides
BUY = 0
SELL = 1

# ClobAuth EIP-712 types
CLOB_AUTH_DOMAIN = {
    "name": "ClobAuthDomain",
    "version": "1",
    "chainId": CHAIN_ID,
}

CLOB_AUTH_TYPES = {
    "ClobAuth": [
        {"name": "address", "type": "address"},
        {"name": "timestamp", "type": "string"},
        {"name": "nonce", "type": "uint256"},
        {"name": "message", "type": "string"},
    ],
}

CLOB_AUTH_MESSAGE_TEXT = "This message attests that I control the given wallet"

# Order EIP-712 types
ORDER_TYPES = {
    "Order": [
        {"name": "salt", "type": "uint256"},
        {"name": "maker", "type": "address"},
        {"name": "signer", "type": "address"},
        {"name": "taker", "type": "address"},
        {"name": "tokenId", "type": "uint256"},
        {"name": "makerAmount", "type": "uint256"},
        {"name": "takerAmount", "type": "uint256"},
        {"name": "expiration", "type": "uint256"},
        {"name": "nonce", "type": "uint256"},
        {"name": "feeRateBps", "type": "uint256"},
        {"name": "side", "type": "uint8"},
        {"name": "signatureType", "type": "uint8"},
    ],
}

# Tick size rounding config: {tick_size: (price_decimals, size_decimals)}
ROUNDING_CONFIG: dict[str, tuple[int, int]] = {
    "0.1": (1, 3),
    "0.01": (2, 4),
    "0.001": (3, 5),
    "0.0001": (4, 6),
}

USDC_DECIMALS = 6


def _generate_salt() -> int:
    """Generate a cryptographically random salt for orders."""
    return int.from_bytes(os.urandom(8), "big")


def _round_down(value: float, decimals: int) -> float:
    """Round a value down to the specified decimal places."""
    factor = 10**decimals
    return math.floor(value * factor) / factor


def _round_normal(value: float, decimals: int) -> float:
    """Round a value to the specified decimal places."""
    return round(value, decimals)


def _to_token_decimals(value: float, decimals: int = USDC_DECIMALS) -> int:
    """Convert a decimal value to token units."""
    return int(value * (10**decimals))


def get_order_amounts(
    side: int,
    price: float,
    size: float,
    tick_size: str = "0.01",
) -> tuple[int, int]:
    """Calculate maker and taker amounts for an order.

    Args:
        side: BUY (0) or SELL (1)
        price: Price between 0 and 1
        size: Number of shares
        tick_size: Minimum price increment

    Returns:
        Tuple of (maker_amount, taker_amount) in token decimals
    """
    price_decimals, size_decimals = ROUNDING_CONFIG.get(tick_size, (2, 4))

    price = _round_normal(price, price_decimals)
    size = _round_down(size, size_decimals)

    raw_maker = size * price if side == BUY else size
    raw_taker = size if side == BUY else size * price

    maker_amount = _to_token_decimals(_round_down(raw_maker, size_decimals + 1))
    taker_amount = _to_token_decimals(_round_down(raw_taker, size_decimals + 1))

    return maker_amount, taker_amount


def build_hmac_signature(
    secret: str,
    timestamp: int,
    method: str,
    request_path: str,
    body: str = "",
) -> str:
    """Build HMAC-SHA256 signature for CLOB API L2 auth."""
    message = str(timestamp) + method.upper() + request_path
    if body:
        # Quote normalization required for cross-language compatibility
        message += body.replace("'", '"')

    decoded_secret = base64.urlsafe_b64decode(secret)
    hmac_obj = hmac.new(decoded_secret, message.encode(), hashlib.sha256)
    return base64.urlsafe_b64encode(hmac_obj.digest()).decode()


def _get_signature_hex(signed: Any) -> str:
    """Extract hex signature string from a signed message, with 0x prefix."""
    sig = (
        signed.signature.hex()
        if hasattr(signed.signature, "hex")
        else str(signed.signature)
    )
    if not sig.startswith("0x"):
        sig = "0x" + sig
    return sig


async def _http_get(
    url: str, params: dict[str, Any] | None = None, **kwargs: Any
) -> Any:
    """Shared GET helper using httpx."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, **kwargs)
        if resp.status_code != 200:
            raise ToolException(f"API error {resp.status_code}: {resp.text[:200]}")
        return resp.json()


async def _http_request(
    method: str,
    url: str,
    headers: dict[str, str],
    body_str: str | None = None,
    accept_statuses: tuple[int, ...] = (200,),
) -> Any:
    """Shared request helper using httpx."""
    async with httpx.AsyncClient() as client:
        kwargs: dict[str, Any] = {"headers": headers}
        if body_str:
            kwargs["content"] = body_str
        resp = await client.request(method, url, **kwargs)
        if resp.status_code not in accept_statuses:
            raise ToolException(f"API error {resp.status_code}: {resp.text[:200]}")
        return resp.json()


class PolymarketBaseTool(IntentKitOnChainSkill):
    """Base class for Polymarket skills.

    Inherits IntentKitOnChainSkill for unified wallet signing support.
    Provides HTTP helpers for Gamma, CLOB, and Data APIs,
    and order signing via EIP-712.
    """

    category: str = "polymarket"

    def _require_wallet(self, action: str = "perform this action") -> None:
        """Validate the agent has a signing-capable wallet.

        Raises ToolException if not.
        """
        if not self.is_onchain_capable():
            raise ToolException(
                f"Agent wallet is not configured to {action}. "
                "Configure a CDP, Native, Safe, or Privy wallet."
            )

    # --- Public API helpers ---

    async def _gamma_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET request to Gamma API (no auth required)."""
        return await _http_get(f"{GAMMA_URL}{path}", params=params)

    async def _clob_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET request to CLOB API (no auth required)."""
        return await _http_get(f"{CLOB_URL}{path}", params=params)

    async def _data_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET request to Data API (no auth required)."""
        return await _http_get(f"{DATA_URL}{path}", params=params)

    # --- L1 Auth: derive API credentials via EIP-712 ---

    async def _ensure_api_creds(self) -> dict[str, str]:
        """Ensure API credentials exist, derive them if not.

        Returns dict with keys: api_key, api_secret, api_passphrase, wallet_address
        """
        cached = await self.get_agent_skill_data_raw(self.category, "api_creds")
        if cached and all(
            k in cached
            for k in ("api_key", "api_secret", "api_passphrase", "wallet_address")
        ):
            return cached

        signer = await self.get_wallet_signer()
        wallet_address = signer.address
        timestamp = str(int(time.time()))
        nonce = 0

        signed = signer.sign_typed_data(
            domain_data=CLOB_AUTH_DOMAIN,
            message_types=CLOB_AUTH_TYPES,
            message_data={
                "address": wallet_address,
                "timestamp": timestamp,
                "nonce": nonce,
                "message": CLOB_AUTH_MESSAGE_TEXT,
            },
        )

        url = f"{CLOB_URL}/auth/api-key"
        headers = {
            "POLY_ADDRESS": wallet_address,
            "POLY_SIGNATURE": _get_signature_hex(signed),
            "POLY_TIMESTAMP": timestamp,
            "POLY_NONCE": str(nonce),
        }

        result = await _http_get(url, headers=headers)

        creds = {
            "api_key": result.get("apiKey") or result.get("api_key", ""),
            "api_secret": result.get("secret") or result.get("api_secret", ""),
            "api_passphrase": result.get("passphrase")
            or result.get("api_passphrase", ""),
            "wallet_address": wallet_address,
        }

        await self.save_agent_skill_data_raw(self.category, "api_creds", creds)
        return creds

    # --- L2 Auth: HMAC-signed requests ---

    def _build_auth_headers(
        self,
        creds: dict[str, str],
        method: str,
        path: str,
        body: str = "",
    ) -> dict[str, str]:
        """Build POLY_* HMAC auth headers."""
        timestamp = int(time.time())
        signature = build_hmac_signature(
            creds["api_secret"], timestamp, method, path, body
        )
        return {
            "POLY_ADDRESS": creds["wallet_address"],
            "POLY_SIGNATURE": signature,
            "POLY_TIMESTAMP": str(timestamp),
            "POLY_API_KEY": creds["api_key"],
            "POLY_PASSPHRASE": creds["api_passphrase"],
        }

    async def _clob_auth_get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> Any:
        """Authenticated GET to CLOB API."""
        creds = await self._ensure_api_creds()
        full_path = path
        if params:
            qs = str(httpx.QueryParams(params))
            full_path = f"{path}?{qs}"

        headers = self._build_auth_headers(creds, "GET", full_path)
        return await _http_get(f"{CLOB_URL}{path}", params=params, headers=headers)

    async def _clob_auth_post(self, path: str, body: dict[str, Any]) -> Any:
        """Authenticated POST to CLOB API."""
        creds = await self._ensure_api_creds()
        body_str = json.dumps(body, separators=(",", ":"))
        headers = self._build_auth_headers(creds, "POST", path, body_str)
        headers["Content-Type"] = "application/json"
        return await _http_request(
            "POST", f"{CLOB_URL}{path}", headers, body_str, (200, 201)
        )

    async def _clob_auth_delete(
        self, path: str, body: dict[str, Any] | None = None
    ) -> Any:
        """Authenticated DELETE to CLOB API."""
        creds = await self._ensure_api_creds()
        body_str = json.dumps(body, separators=(",", ":")) if body else None
        headers = self._build_auth_headers(creds, "DELETE", path, body_str or "")
        if body:
            headers["Content-Type"] = "application/json"
        return await _http_request("DELETE", f"{CLOB_URL}{path}", headers, body_str)

    # --- Order signing ---

    async def _sign_order(
        self,
        token_id: str,
        side: int,
        price: float,
        size: float,
        tick_size: str = "0.01",
        neg_risk: bool = False,
        expiration: int = 0,
    ) -> dict[str, Any]:
        """Build and sign an order using EIP-712.

        Returns a dict ready to POST to /order endpoint.
        """
        signer = await self.get_wallet_signer()
        signer_address = signer.address

        # For Safe/Privy wallets, maker (funds holder) differs from signer (EOA)
        wallet_provider = self.get_agent_wallet_provider_type()
        if wallet_provider in ("safe", "privy"):
            provider = await self.get_wallet_provider()
            maker_address = provider.get_address()
            sig_type = (
                SIG_POLY_GNOSIS_SAFE if wallet_provider == "safe" else SIG_POLY_PROXY
            )
        else:
            maker_address = signer_address
            sig_type = SIG_EOA

        exchange = NEG_RISK_EXCHANGE_ADDRESS if neg_risk else EXCHANGE_ADDRESS
        maker_amount, taker_amount = get_order_amounts(side, price, size, tick_size)

        salt = _generate_salt()
        nonce = 0
        fee_rate_bps = 0

        try:
            fee_data = await self._clob_get(f"/fee-rate/{token_id}")
            fee_rate_bps = int(fee_data.get("fee_rate_bps", 0))
        except Exception:
            logger.warning("Failed to get fee rate for %s, using 0", token_id)

        order_domain = {
            "name": "Polymarket CTF Exchange",
            "version": "1",
            "chainId": CHAIN_ID,
            "verifyingContract": exchange,
        }

        order_data = {
            "salt": salt,
            "maker": maker_address,
            "signer": signer_address,
            "taker": ZERO_ADDRESS,
            "tokenId": int(token_id),
            "makerAmount": maker_amount,
            "takerAmount": taker_amount,
            "expiration": expiration,
            "nonce": nonce,
            "feeRateBps": fee_rate_bps,
            "side": side,
            "signatureType": sig_type,
        }

        signed = signer.sign_typed_data(
            domain_data=order_domain,
            message_types=ORDER_TYPES,
            message_data=order_data,
        )

        signature = _get_signature_hex(signed)

        return {
            "order": {
                "salt": salt,
                "maker": maker_address,
                "signer": signer_address,
                "taker": ZERO_ADDRESS,
                "tokenId": str(token_id),
                "makerAmount": str(maker_amount),
                "takerAmount": str(taker_amount),
                "expiration": str(expiration),
                "nonce": str(nonce),
                "feeRateBps": str(fee_rate_bps),
                "side": "BUY" if side == BUY else "SELL",
                "signatureType": sig_type,
                "signature": signature,
            },
            "orderType": "GTC",
        }
