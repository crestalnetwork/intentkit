"""The x402 client's payment cap must stay the caller's ``max_value``.

x402 2.20 enabled client spend controls by default — SDK default assets only,
capped at $1 per payment — enforced during requirement selection, before any
registered policy runs. That default silently overrides the cap the agent
chose, so ``_build_x402_client`` turns it off; these tests pin that down so a
future SDK bump cannot quietly reinstate a $1 ceiling.

They drive the same public entry point production does —
``create_payment_payload`` (``X402CompatTransport.handle_async_request``) —
rather than the selection helper underneath it, so enforcement moving
elsewhere on that path still trips them.
"""

from typing import Any

import pytest
from x402 import NoMatchingRequirementsError
from x402.schemas import PaymentRequired, PaymentRequirements

from intentkit.tools.x402.httpx_compat import _build_x402_client

# USDC on Base — in the SDK's own default-asset table (which is what spend
# controls allowlist against, not our catalog), 6 decimals, so $1 is 1_000_000
# base units.
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
BASE_NETWORK = "eip155:8453"
ONE_USDC = 1_000_000


class _StubSigner:
    """Stand-in for the team wallet signer IntentKitEvmSignerAdapter wraps.

    Reaching a payload means the adapter ran, so the signature has to be
    bytes-shaped; nothing here verifies it.
    """

    address = "0x000000000000000000000000000000000000dEaD"

    def sign_typed_data(self, **_: Any) -> bytes:
        return b"\x11" * 65


def _payment_required(amount: int, asset: str = USDC_BASE) -> PaymentRequired:
    return PaymentRequired(
        x402_version=2,
        accepts=[
            PaymentRequirements(
                scheme="exact",
                network=BASE_NETWORK,
                amount=str(amount),
                pay_to="0x0000000000000000000000000000000000000001",
                max_timeout_seconds=60,
                asset=asset,
                extra={"name": "USDC", "version": "2"},
            )
        ],
    )


async def _pay(client: Any, amount: int, asset: str = USDC_BASE) -> Any:
    payload = await client.create_payment_payload(_payment_required(amount, asset))
    return payload.accepted


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", [ONE_USDC + 1, 9 * ONE_USDC])
async def test_payments_over_one_dollar_are_paid_up_to_max_value(amount: int):
    """Just over the SDK's $1 default, and well over it, both still pay."""
    client = _build_x402_client(_StubSigner(), max_value=10 * ONE_USDC)
    assert (await _pay(client, amount)).amount == str(amount)


@pytest.mark.asyncio
async def test_payment_above_max_value_is_rejected():
    """The caller's cap is still enforced — by the max_amount policy."""
    client = _build_x402_client(_StubSigner(), max_value=ONE_USDC)
    with pytest.raises(NoMatchingRequirementsError):
        await _pay(client, 2 * ONE_USDC)


@pytest.mark.asyncio
async def test_no_max_value_leaves_the_payment_uncapped():
    """x402_http_request registers no policy; it must stay uncapped, not $1."""
    client = _build_x402_client(_StubSigner(), max_value=None)
    assert (await _pay(client, 500 * ONE_USDC)).amount == str(500 * ONE_USDC)


@pytest.mark.asyncio
async def test_asset_outside_the_sdk_default_table_is_still_payable():
    """Spend controls also allowlist assets; agents may pay in other tokens."""
    client = _build_x402_client(_StubSigner(), max_value=10 * ONE_USDC)
    unknown_token = "0x1234567890123456789012345678901234567890"
    assert (await _pay(client, ONE_USDC, asset=unknown_token)).asset == unknown_token
