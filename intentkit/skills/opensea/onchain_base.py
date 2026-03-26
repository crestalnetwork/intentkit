"""OpenSea on-chain base class with Seaport protocol helpers."""

import logging
import secrets
import time
from typing import Any

from langchain_core.tools.base import ToolException
from web3 import Web3

from intentkit.skills.onchain import IntentKitOnChainSkill
from intentkit.skills.opensea.base import OpenSeaApiMixin
from intentkit.skills.opensea.constants import (
    ERC721_APPROVAL_ABI,
    ITEM_TYPE_ERC721,
    ITEM_TYPE_NATIVE,
    NETWORK_TO_CHAIN,
    OPENSEA_CONDUIT_ADDRESS,
    OPENSEA_CONDUIT_KEY,
    OPENSEA_FEE_BPS,
    OPENSEA_FEE_RECIPIENT,
    OPENSEA_ZONE_ADDRESS,
    ORDER_TYPE_FULL_RESTRICTED,
    SEAPORT_ABI,
    SEAPORT_ADDRESS,
    SEAPORT_EIP712_DOMAIN,
    SEAPORT_ORDER_TYPES,
    ZERO_ADDRESS,
    ZERO_BYTES32,
)

logger = logging.getLogger(__name__)


class OpenSeaOnChainBaseTool(OpenSeaApiMixin, IntentKitOnChainSkill):
    """Base class for OpenSea on-chain skills (listing, buying, canceling)."""

    category: str = "opensea"

    def _get_chain_name(self) -> str:
        """Get OpenSea chain name from agent network_id."""
        network_id = self.get_agent_network_id()
        if not network_id:
            raise ToolException("Agent network_id is not configured")
        chain = NETWORK_TO_CHAIN.get(network_id)
        if not chain:
            raise ToolException(
                f"Network {network_id} is not supported by OpenSea. "
                f"Supported: {', '.join(NETWORK_TO_CHAIN.keys())}"
            )
        return chain

    async def _get_seaport_counter(self, offerer: str) -> int:
        """Get the current Seaport counter for an address."""
        w3 = self.web3_client()
        seaport = w3.eth.contract(
            address=Web3.to_checksum_address(SEAPORT_ADDRESS),
            abi=SEAPORT_ABI,
        )
        counter = await seaport.functions.getCounter(
            Web3.to_checksum_address(offerer)
        ).call()
        return counter

    async def _ensure_nft_approval(
        self, contract_address: str, owner_address: str
    ) -> str | None:
        """Ensure the NFT contract is approved for OpenSea conduit.

        Returns:
            Transaction hash if approval was sent, None if already approved.
        """
        w3 = self.web3_client()
        wallet = await self.get_unified_wallet()

        nft_contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=ERC721_APPROVAL_ABI,
        )
        is_approved = await nft_contract.functions.isApprovedForAll(
            Web3.to_checksum_address(owner_address),
            Web3.to_checksum_address(OPENSEA_CONDUIT_ADDRESS),
        ).call()

        if is_approved:
            return None

        approve_data = nft_contract.encode_abi(
            "setApprovalForAll",
            [Web3.to_checksum_address(OPENSEA_CONDUIT_ADDRESS), True],
        )
        tx_hash = await wallet.send_transaction(
            to=Web3.to_checksum_address(contract_address),
            data=approve_data,
        )
        receipt = await wallet.wait_for_receipt(tx_hash)
        if receipt.get("status", 0) != 1:
            raise ToolException(f"NFT approval transaction failed. Hash: {tx_hash}")
        return tx_hash

    def _build_listing_order(
        self,
        offerer: str,
        contract_address: str,
        token_id: str,
        price_wei: int,
        expiration_hours: int,
        counter: int,
    ) -> dict[str, Any]:
        """Build Seaport OrderComponents for a listing."""
        start_time = int(time.time())
        end_time = start_time + (expiration_hours * 3600)
        salt = secrets.randbelow(2**256)

        fee_amount = (price_wei * OPENSEA_FEE_BPS) // 10000
        seller_amount = price_wei - fee_amount

        return {
            "offerer": Web3.to_checksum_address(offerer),
            "zone": Web3.to_checksum_address(OPENSEA_ZONE_ADDRESS),
            "offer": [
                {
                    "itemType": ITEM_TYPE_ERC721,
                    "token": Web3.to_checksum_address(contract_address),
                    "identifierOrCriteria": int(token_id),
                    "startAmount": 1,
                    "endAmount": 1,
                }
            ],
            "consideration": [
                {
                    "itemType": ITEM_TYPE_NATIVE,
                    "token": Web3.to_checksum_address(ZERO_ADDRESS),
                    "identifierOrCriteria": 0,
                    "startAmount": seller_amount,
                    "endAmount": seller_amount,
                    "recipient": Web3.to_checksum_address(offerer),
                },
                {
                    "itemType": ITEM_TYPE_NATIVE,
                    "token": Web3.to_checksum_address(ZERO_ADDRESS),
                    "identifierOrCriteria": 0,
                    "startAmount": fee_amount,
                    "endAmount": fee_amount,
                    "recipient": Web3.to_checksum_address(OPENSEA_FEE_RECIPIENT),
                },
            ],
            "orderType": ORDER_TYPE_FULL_RESTRICTED,
            "startTime": start_time,
            "endTime": end_time,
            "zoneHash": ZERO_BYTES32,
            "salt": salt,
            "conduitKey": OPENSEA_CONDUIT_KEY,
            "totalOriginalConsiderationItems": 2,
            "counter": counter,
        }

    async def _sign_seaport_order(self, order_parameters: dict[str, Any]) -> str:
        """Sign a Seaport order using EIP-712 typed data.

        Returns:
            The signature hex string.
        """
        signer = await self.get_wallet_signer()
        w3 = self.web3_client()
        chain_id = await w3.eth.chain_id

        domain = {
            **SEAPORT_EIP712_DOMAIN,
            "chainId": chain_id,
            "verifyingContract": Web3.to_checksum_address(SEAPORT_ADDRESS),
        }

        # order_parameters already matches the EIP-712 message structure
        signed = signer.sign_typed_data(
            domain_data=domain,
            message_types=SEAPORT_ORDER_TYPES,
            message_data=order_parameters,
        )
        return signed.signature.hex()
