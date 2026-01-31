"""
Base class for x402 skills with unified wallet provider support.

This module provides the X402BaseSkill class which supports
CDP, Privy, and Safe wallet providers for x402 payment protocol operations.
"""

import base64
import json
import logging
from typing import Any

import httpx
from eth_abi import encode
from eth_utils import keccak, to_checksum_address
from x402.schemas import PaymentRequired, PaymentRequiredV1

from intentkit.clients.privy import CHAIN_CONFIGS, PrivyClient, transfer_erc20_gasless
from intentkit.config.config import config
from intentkit.models.agent_data import AgentData
from intentkit.models.x402_order import X402Order, X402OrderCreate
from intentkit.skills.onchain import IntentKitOnChainSkill

logger = logging.getLogger(__name__)

# Common HTTP status code descriptions
HTTP_STATUS_PHRASES: dict[int, str] = {
    200: "OK",
    201: "Created",
    202: "Accepted",
    204: "No Content",
    301: "Moved Permanently",
    302: "Found",
    304: "Not Modified",
    400: "Bad Request",
    401: "Unauthorized",
    402: "Payment Required",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    408: "Request Timeout",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}

# Maximum content length to return (in bytes)
MAX_CONTENT_LENGTH = 1000
DEFAULT_NETWORK_ID = "base-mainnet"
SUPPORTED_WALLET_PROVIDERS = {"cdp", "safe", "privy"}

PAYMENT_RESPONSE_HEADERS = ("payment-response", "x-payment-response")
PAYMENT_REQUIRED_HEADERS = ("payment-required",)
PAYMENT_SIGNATURE_HEADERS = ("payment-signature", "x-payment")

CAIP2_NETWORK_TO_AGENT_NETWORK: dict[str, str] = {
    "eip155:1": "ethereum-mainnet",
    "eip155:8453": "base-mainnet",
    "eip155:84532": "base-sepolia",
    "eip155:137": "polygon-mainnet",
    "eip155:43114": "avalanche-mainnet",
}


def get_payment_response_header(response: httpx.Response) -> str | None:
    """Get the x402 payment response header value (v1 or v2)."""
    for header in PAYMENT_RESPONSE_HEADERS:
        value = response.headers.get(header)
        if value:
            return value
    return None


def get_payment_required_header(response: httpx.Response) -> str | None:
    """Get the x402 payment required header value (v2)."""
    for header in PAYMENT_REQUIRED_HEADERS:
        value = response.headers.get(header)
        if value:
            return value
    return None


def decode_payment_response_header(
    payment_response_header: str,
) -> dict[str, Any] | None:
    """Decode the base64-encoded payment response header into JSON."""
    try:
        return json.loads(base64.b64decode(payment_response_header))
    except (json.JSONDecodeError, ValueError):
        return None


def decode_payment_required_header(
    payment_required_header: str,
) -> dict[str, Any] | None:
    """Decode the base64-encoded payment required header into JSON."""
    try:
        return json.loads(base64.b64decode(payment_required_header))
    except (json.JSONDecodeError, ValueError):
        return None


def get_payment_signature_header(headers: Any) -> str | None:
    """Get the x402 payment signature header value (v1 or v2)."""
    for header in PAYMENT_SIGNATURE_HEADERS:
        value = headers.get(header)
        if value:
            return value
    return None


def decode_payment_signature_header(
    payment_signature_header: str,
) -> dict[str, Any] | None:
    """Decode the base64-encoded payment signature header into JSON."""
    try:
        return json.loads(base64.b64decode(payment_signature_header))
    except (json.JSONDecodeError, ValueError):
        return None


def normalize_payment_required_payload(
    payload: dict[str, Any], default_version: int = 1
) -> dict[str, Any]:
    """Normalize v1/v2 payment required payloads for x402 parsing."""
    normalized = dict(payload)
    x402_version = normalized.get("x402Version") or normalized.get("x402_version")
    if x402_version is None:
        normalized["x402Version"] = default_version
    else:
        normalized["x402Version"] = x402_version
    normalized.setdefault("error", "")
    return normalized


def normalize_network_id(network: str | None) -> str | None:
    """Normalize CAIP-2 network identifiers to agent network IDs."""
    if not network:
        return None
    key = str(network).strip().lower()
    return CAIP2_NETWORK_TO_AGENT_NETWORK.get(key) or network


def _extract_requirement_amount(requirement: Any) -> int:
    """Extract integer amount from v1/v2 payment requirements."""
    amount_value = getattr(requirement, "amount", None)
    if amount_value is None:
        amount_value = getattr(requirement, "max_amount_required", None)
    if amount_value is None:
        raise ValueError("Payment requirement missing amount value.")
    try:
        return int(amount_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Payment amount must be a valid integer, got "
            f"{amount_value} ({type(amount_value).__name__})."
        ) from exc


def get_status_text(status_code: int) -> str:
    """Get human-readable status text for an HTTP status code."""
    phrase = HTTP_STATUS_PHRASES.get(status_code)
    if phrase:
        return f"{status_code} {phrase}"
    # Fallback for unknown codes
    if 100 <= status_code < 200:
        return f"{status_code} Informational"
    elif 200 <= status_code < 300:
        return f"{status_code} Success"
    elif 300 <= status_code < 400:
        return f"{status_code} Redirect"
    elif 400 <= status_code < 500:
        return f"{status_code} Client Error"
    elif 500 <= status_code < 600:
        return f"{status_code} Server Error"
    return str(status_code)


def truncate_content(content: str, max_length: int = MAX_CONTENT_LENGTH) -> str:
    """Truncate content to max_length bytes, adding ellipsis if truncated."""
    content_bytes = content.encode("utf-8")
    if len(content_bytes) <= max_length:
        return content
    # Truncate and decode safely (may cut multi-byte chars)
    truncated = content_bytes[:max_length].decode("utf-8", errors="ignore")
    return truncated + "... [truncated]"


class X402BaseSkill(IntentKitOnChainSkill):
    """
    Base class for x402 skills.

    This class provides unified wallet signer support for x402 operations,
    automatically selecting the appropriate signer based on the agent's
    wallet_provider configuration (CDP, Privy, or Safe).

    Safe wallet mode is supported by prefunding the Privy EOA signer
    before initiating an x402 payment.
    """

    category: str = "x402"

    def _validate_wallet_provider(self) -> None:
        """Validate that the wallet provider supports x402 operations.

        Raises:
            ValueError: If wallet provider is not supported for x402.
        """
        agent = self.get_context().agent
        if agent and agent.wallet_provider not in SUPPORTED_WALLET_PROVIDERS:
            raise ValueError(
                "x402 operations require wallet_provider to be 'cdp', 'safe', or 'privy'."
            )

    async def get_signer(self) -> Any:
        """
        Get the wallet signer for x402 operations.

        This method uses the unified wallet signer interface from
        IntentKitOnChainSkill, which automatically selects:
        - ThreadSafeEvmWalletSigner for CDP wallets
        - PrivyWalletSigner for Privy and Safe wallets

        Both signers implement the required interface for x402:
        - address property
        - sign_message()
        - sign_typed_data()
        - unsafe_sign_hash()

        Returns:
            A wallet signer compatible with x402 requirements.

        Raises:
            ValueError: If wallet provider is unsupported.
        """
        # Validate wallet provider before getting signer
        self._validate_wallet_provider()
        return await self.get_wallet_signer()

    async def _get_payment_requirement(
        self,
        method: str,
        request_kwargs: dict[str, Any],
        timeout: float,
    ) -> PaymentRequired | PaymentRequiredV1 | None:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method, **request_kwargs)
            if response.status_code != 402:
                return None

            payment_required_header = get_payment_required_header(response)
            if payment_required_header:
                payment_data = decode_payment_required_header(payment_required_header)
                if not payment_data:
                    raise ValueError("Failed to decode payment required header.")
                default_version = 2
            else:
                try:
                    payment_data = response.json()
                except ValueError as exc:
                    raise ValueError(
                        "Failed to parse payment required response body."
                    ) from exc
                default_version = 1

            try:
                normalized = normalize_payment_required_payload(
                    payment_data, default_version=default_version
                )
                version = normalized.get("x402Version") or normalized.get(
                    "x402_version"
                )
                if version == 1:
                    return PaymentRequiredV1.model_validate(normalized)
                return PaymentRequired.model_validate(normalized)
            except Exception as exc:
                raise ValueError(
                    f"Failed to parse payment requirements: {exc}"
                ) from exc

    @staticmethod
    def _select_payment_requirement(
        payment_response: PaymentRequired | PaymentRequiredV1,
    ) -> Any | None:
        if not payment_response.accepts:
            return None
        for requirement in payment_response.accepts:
            scheme = (requirement.scheme or "").lower()
            if scheme in {"exact", "eip3009"}:
                return requirement
        return payment_response.accepts[0]

    def _resolve_rpc_url(
        self,
        network_id: str,
        privy_wallet_data: dict[str, Any],
    ) -> str:
        normalized_network_id = normalize_network_id(network_id) or network_id
        rpc_url = privy_wallet_data.get("rpc_url")
        if not rpc_url and config.chain_provider:
            try:
                chain_config = config.chain_provider.get_chain_config(
                    normalized_network_id
                )
                rpc_url = chain_config.rpc_url
            except Exception as exc:
                logger.warning("Failed to get RPC URL from chain provider: %s", exc)
        if not rpc_url:
            chain_config = CHAIN_CONFIGS.get(normalized_network_id)
            if chain_config and chain_config.rpc_url:
                rpc_url = chain_config.rpc_url
        if not rpc_url:
            raise ValueError(
                f"RPC URL not configured for network {normalized_network_id}"
            )
        return rpc_url

    async def _get_erc20_balance(
        self,
        rpc_url: str,
        token_address: str,
        wallet_address: str,
    ) -> int:
        balance_selector = keccak(text="balanceOf(address)")[:4]
        call_data = balance_selector + encode(
            ["address"], [to_checksum_address(wallet_address)]
        )
        async with httpx.AsyncClient() as client:
            response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [
                        {
                            "to": to_checksum_address(token_address),
                            "data": "0x" + call_data.hex(),
                        },
                        "latest",
                    ],
                    "id": 1,
                },
                timeout=30.0,
            )
        if response.status_code != 200:
            raise ValueError(
                f"Failed to get token balance: HTTP {response.status_code}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ValueError("Failed to decode token balance response.") from exc
        result = payload.get("result")
        if not isinstance(result, str):
            raise ValueError("Token balance response missing result.")
        try:
            return int(result, 16)
        except ValueError as exc:
            raise ValueError("Token balance response is not valid hex.") from exc

    async def _ensure_safe_funding(
        self,
        *,
        amount: int,
        token_address: str,
        max_value: int | None = None,
        network: str | None = None,
    ) -> None:
        agent = self.get_context().agent
        if not agent or agent.wallet_provider != "safe":
            return
        if amount <= 0:
            return
        if max_value is not None and amount > max_value:
            raise ValueError(f"Payment amount {amount} exceeds max_value {max_value}.")

        agent_data = await AgentData.get(agent.id)
        if not agent_data.privy_wallet_data:
            raise ValueError("Privy wallet data missing for Safe wallet funding.")
        try:
            privy_wallet_data = json.loads(agent_data.privy_wallet_data)
        except json.JSONDecodeError as exc:
            raise ValueError("Privy wallet data is corrupted.") from exc

        try:
            privy_wallet_id = privy_wallet_data["privy_wallet_id"]
            privy_wallet_address = privy_wallet_data["privy_wallet_address"]
            safe_address = privy_wallet_data["smart_wallet_address"]
        except KeyError as exc:
            raise ValueError("Privy wallet data missing required fields.") from exc
        network_id = (
            privy_wallet_data.get("network_id")
            or agent.network_id
            or network
            or DEFAULT_NETWORK_ID
        )
        normalized_network_id = normalize_network_id(network_id) or network_id
        rpc_url = self._resolve_rpc_url(normalized_network_id, privy_wallet_data)
        balance = await self._get_erc20_balance(
            rpc_url=rpc_url,
            token_address=token_address,
            wallet_address=privy_wallet_address,
        )
        if balance >= amount:
            return

        transfer_amount = amount - balance
        logger.info(
            "Funding Privy wallet for x402 payment: required=%s balance=%s transfer=%s",
            amount,
            balance,
            transfer_amount,
        )
        privy_client = PrivyClient()
        await transfer_erc20_gasless(
            privy_client=privy_client,
            privy_wallet_id=privy_wallet_id,
            privy_wallet_address=privy_wallet_address,
            safe_address=safe_address,
            token_address=token_address,
            to=privy_wallet_address,
            amount=transfer_amount,
            network_id=normalized_network_id,
            rpc_url=rpc_url,
        )

    async def _prefund_safe_wallet(
        self,
        *,
        method: str,
        request_kwargs: dict[str, Any],
        timeout: float,
        max_value: int | None = None,
    ) -> None:
        agent = self.get_context().agent
        if not agent or agent.wallet_provider != "safe":
            return
        payment_response = await self._get_payment_requirement(
            method=method,
            request_kwargs=request_kwargs,
            timeout=timeout,
        )
        if payment_response is None:
            return
        requirement = self._select_payment_requirement(payment_response)
        if requirement is None:
            return
        if not requirement.asset:
            raise ValueError("Payment requirement missing asset address.")
        amount = _extract_requirement_amount(requirement)
        normalized_network = normalize_network_id(getattr(requirement, "network", None))
        logger.debug(
            "x402 payment requirement: scheme=%s network=%s asset=%s amount=%s",
            getattr(requirement, "scheme", None),
            normalized_network or getattr(requirement, "network", None),
            requirement.asset,
            amount,
        )
        await self._ensure_safe_funding(
            amount=amount,
            token_address=requirement.asset,
            max_value=max_value,
            network=normalized_network or getattr(requirement, "network", None),
        )

    def format_response(self, response: httpx.Response) -> str:
        """
        Format an HTTP response for skill output.

        Includes:
        - Human-readable status code
        - Chain/network and tx hash from payment response (if available)
        - Truncated content (max 1000 bytes)

        Args:
            response: The HTTP response to format

        Returns:
            Formatted response string
        """
        lines = [f"Status: {get_status_text(response.status_code)}"]

        # Extract chain and tx_hash from payment response header (v1/v2)
        payment_response_header = get_payment_response_header(response)
        if payment_response_header:
            payment_data = decode_payment_response_header(payment_response_header)
            if payment_data:
                network = payment_data.get("network")
                tx_hash = payment_data.get("transaction") or payment_data.get("txHash")
                if network:
                    lines.append(f"Chain: {network}")
                if tx_hash:
                    lines.append(f"TxHash: {tx_hash}")

        # Truncate content if too long
        content = truncate_content(response.text)
        lines.append(f"Content: {content}")

        return "\n".join(lines)

    async def record_order(
        self,
        response: httpx.Response,
        skill_name: str,
        method: str,
        url: str,
        max_value: int | None = None,
        pay_to_fallback: str | None = None,
    ) -> None:
        """
        Record an x402 order from a successful payment response.

        Extracts payment information from the PAYMENT-RESPONSE header
        and creates an order record in the database.

        Args:
            response: The HTTP response from the x402 request
            skill_name: Name of the skill that made the request
            method: HTTP method used
            url: Target URL
            max_value: Maximum payment value (for x402_pay only)
            pay_to_fallback: Fallback address if pay_to is missing in headers
        """
        try:
            # Get context info
            context = self.get_context()
            agent_id = context.agent_id
            chat_id = context.chat_id
            user_id = context.user_id

            # Get payer address from signer
            signer = await self.get_signer()
            payer = signer.address

            # Derive task_id from chat_id for autonomous tasks
            task_id = None
            if chat_id.startswith("autonomous-"):
                task_id = chat_id.removeprefix("autonomous-")

            # Parse payment response header (v1/v2, base64-encoded JSON)
            payment_response_header = get_payment_response_header(response)
            if not payment_response_header:
                logger.debug("No payment response header found, skipping order record")
                return

            payment_data = decode_payment_response_header(payment_response_header)
            if not payment_data:
                logger.warning("Failed to parse payment response header.")
                return

            # Extract payment details
            amount = payment_data.get("amount")
            asset = payment_data.get("asset")
            network = payment_data.get("network")
            pay_to = payment_data.get("payTo", payment_data.get("pay_to"))
            description = payment_data.get("description")

            accepted_from_response = payment_data.get("accepted")
            if isinstance(accepted_from_response, dict):
                amount = (
                    amount
                    or accepted_from_response.get("amount")
                    or accepted_from_response.get("maxAmountRequired")
                )
                asset = asset or accepted_from_response.get("asset")
                network = network or accepted_from_response.get("network")
                pay_to = (
                    pay_to
                    or accepted_from_response.get("payTo")
                    or accepted_from_response.get("pay_to")
                )

            if response.request:
                signature_header = get_payment_signature_header(
                    response.request.headers
                )
                if signature_header:
                    signature_data = decode_payment_signature_header(signature_header)
                    if isinstance(signature_data, dict):
                        accepted = signature_data.get("accepted")
                        if isinstance(accepted, dict):
                            amount = (
                                amount
                                or accepted.get("amount")
                                or accepted.get("maxAmountRequired")
                            )
                            asset = asset or accepted.get("asset")
                            network = network or accepted.get("network")
                            pay_to = (
                                pay_to
                                or accepted.get("payTo")
                                or accepted.get("pay_to")
                            )
                        if not description:
                            resource = signature_data.get("resource")
                            if isinstance(resource, dict):
                                description = resource.get("description")

            try:
                amount = int(amount) if amount is not None else 0
            except (TypeError, ValueError):
                amount = 0

            asset = asset or "unknown"
            network = normalize_network_id(network) or network or "unknown"

            if not pay_to:
                pay_to = pay_to_fallback or "unknown"

            tx_hash = payment_data.get("transaction", payment_data.get("txHash"))
            success = payment_data.get("success", True)
            description = description

            # Create order record
            order = X402OrderCreate(
                agent_id=agent_id,
                chat_id=chat_id,
                user_id=user_id,
                task_id=task_id,
                skill_name=skill_name,
                method=method,
                url=url,
                max_value=max_value,
                amount=amount,
                asset=asset,
                network=network,
                pay_to=pay_to,
                payer=payer or "unknown",
                tx_hash=tx_hash,
                status="success" if success else "failed",
                error=payment_data.get("errorReason"),
                http_status=response.status_code,
                description=description,
            )
            _ = await X402Order.create(order)
            logger.info(
                f"Recorded x402 order for agent {agent_id}: {tx_hash or 'no tx'}"
            )

        except Exception as e:
            # Don't fail the skill execution if order recording fails
            logger.error(f"Failed to record x402 order: {e}", exc_info=True)
