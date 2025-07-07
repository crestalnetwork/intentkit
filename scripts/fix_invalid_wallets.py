#!/usr/bin/env python3
"""
Script to fix agents with invalid CDP wallet addresses.

This script:
1. Finds agents with cdp_wallet_address that don't exist in CDP
2. Clears their wallet data so they can create new wallets on-demand
3. Provides detailed reporting on what was fixed

Usage:
    python scripts/fix_invalid_wallets.py [--dry-run] [--agent-id AGENT_ID]
"""

import asyncio
import json
import logging
import os
import sys
from typing import List, Optional

# Add the parent directory to the path to import intentkit modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coinbase_agentkit import (
    CdpEvmServerWalletProvider,
    CdpEvmServerWalletProviderConfig,
)
from sqlalchemy import select, update

from intentkit.config.config import config
from intentkit.models.agent_data import AgentDataTable
from intentkit.models.db import get_session, init_db

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WalletFixer:
    """Fixes agents with invalid CDP wallet addresses."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.stats = {
            "total_agents": 0,
            "agents_with_addresses": 0,
            "invalid_addresses": 0,
            "fixed_agents": 0,
            "failed_fixes": 0,
        }

    async def check_wallet_exists(
        self, address: str, network_id: str = "base-mainnet"
    ) -> bool:
        """Check if a wallet address can be initialized with CDP."""
        try:
            # Try to initialize the wallet provider with the address
            wallet_config = CdpEvmServerWalletProviderConfig(
                api_key_id=config.cdp_api_key_name,
                api_key_secret=config.cdp_api_key_private_key,
                network_id=network_id,
                address=address,
                wallet_secret=None,  # We don't need the secret just to check if address exists
            )

            # Try to create the wallet provider - this will fail if address doesn't exist
            CdpEvmServerWalletProvider(wallet_config)  # Just try to initialize it
            return True

        except Exception as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "404" in error_msg:
                return False
            else:
                # For other errors, assume it exists to be safe
                return True

    async def find_agents_with_invalid_wallets(
        self, agent_id: Optional[str] = None
    ) -> List[dict]:
        """Find agents with CDP wallet addresses that don't exist."""
        invalid_agents = []

        async with get_session() as session:
            if agent_id:
                # Check specific agent
                result = await session.execute(
                    select(AgentDataTable).where(AgentDataTable.id == agent_id)
                )
                agents = result.scalars().all()
            else:
                # Check all agents
                result = await session.execute(select(AgentDataTable))
                agents = result.scalars().all()

        for agent in agents:
            self.stats["total_agents"] += 1

            # Extract wallet address from wallet data
            wallet_address = None
            if agent.cdp_wallet_data:
                try:
                    wallet_data = json.loads(agent.cdp_wallet_data)
                    wallet_address = wallet_data.get("default_address_id")
                except (json.JSONDecodeError, AttributeError):
                    pass

            if not wallet_address:
                continue

            self.stats["agents_with_addresses"] += 1

            # Check if wallet exists in CDP
            exists = await self.check_wallet_exists(wallet_address)

            if not exists:
                logger.info(f"Found invalid wallet: {agent.id} -> {wallet_address}")
                self.stats["invalid_addresses"] += 1
                invalid_agents.append(
                    {
                        "id": agent.id,
                        "cdp_wallet_address": wallet_address,
                        "cdp_wallet_data": agent.cdp_wallet_data,
                        "created_at": agent.created_at,
                    }
                )

        return invalid_agents

    async def fix_agent_wallet(self, agent_info: dict) -> bool:
        """Fix a single agent by clearing invalid wallet data."""
        agent_id = agent_info["id"]

        try:
            if not self.dry_run:
                async with get_session() as session:
                    # Clear the invalid wallet data
                    await session.execute(
                        update(AgentDataTable)
                        .where(AgentDataTable.id == agent_id)
                        .values(cdp_wallet_data=None)
                    )
                    await session.commit()

                logger.info(f"Fixed: {agent_id}")
            else:
                logger.info(f"[DRY RUN] Would fix: {agent_id}")

            return True

        except Exception as e:
            logger.error(f"ERROR fixing {agent_id}: {e}")
            return False

    async def run_fix(self, agent_id: Optional[str] = None):
        """Run the wallet fix process."""

        # Find agents with invalid wallets
        invalid_agents = await self.find_agents_with_invalid_wallets(agent_id)

        if not invalid_agents:
            logger.info("No agents with invalid wallet addresses found")
            return

        # Fix each agent
        for agent_info in invalid_agents:
            success = await self.fix_agent_wallet(agent_info)

            if success:
                self.stats["fixed_agents"] += 1
            else:
                self.stats["failed_fixes"] += 1

        self.print_summary()

    def print_summary(self):
        """Log fix statistics."""

        logger.info(
            f"Summary: {self.stats['invalid_addresses']} invalid addresses found, {self.stats['fixed_agents']} fixed"
        )
        if self.dry_run:
            logger.info("*** DRY RUN - NO CHANGES MADE ***")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fix agents with invalid CDP wallet addresses"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without making changes",
    )
    parser.add_argument("--agent-id", type=str, help="Fix only a specific agent by ID")

    args = parser.parse_args()

    # Initialize database connection
    await init_db(
        host=config.db.get("host"),
        username=config.db.get("username"),
        password=config.db.get("password"),
        dbname=config.db.get("dbname"),
        port=config.db.get("port", "5432"),
        auto_migrate=False,
    )

    fixer = WalletFixer(dry_run=args.dry_run)
    await fixer.run_fix(agent_id=args.agent_id)


if __name__ == "__main__":
    asyncio.run(main())
