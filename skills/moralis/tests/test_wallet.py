"""Tests for the Wallet Portfolio skills."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import json
from datetime import datetime, timedelta

from skills.wallet.base import WalletBaseTool
from skills.wallet.api import (
    moralis_fetch_moralis_data,
    moralis_fetch_wallet_balances,
    moralis_fetch_nft_data,
    moralis_fetch_transaction_history,
    get_solana_portfolio,
    get_solana_balance
)
from skills.wallet.moralis_fetch_wallet_portfolio import FetchWalletPortfolio
from skills.wallet.moralis_fetch_chain_portfolio import FetchChainPortfolio
from skills.wallet.moralis_fetch_nft_portfolio import FetchNftPortfolio
from skills.wallet.moralis_fetch_transaction_history import FetchTransactionHistory
from skills.wallet.moralis_fetch_solana_portfolio import FetchSolanaPortfolio
from skills.wallet import get_skills, get_wallet_skill


class DummyResponse:
    """Mock HTTP response for testing."""
    
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json_data = json_data
        self.text = json.dumps(json_data) if json_data else ""

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP Error: {self.status_code}")


class TestWalletBaseClass(unittest.TestCase):
    """Test the base wallet portfolio tool class."""
    
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        self.mock_skill_store = MagicMock()
        self.mock_agent_store = MagicMock()
        self.mock_chain_provider = MagicMock()
    
    def tearDown(self):
        self.loop.close()
    
    def test_base_class_init(self):
        """Test base class initialization."""
        # Create a concrete subclass for testing
        class TestTool(WalletBaseTool):
            async def _arun(self, *args, **kwargs):
                return "test"
        
        tool = TestTool(
            name="test_tool",
            description="Test tool",
            args_schema=MagicMock(),
            api_key="test_key",
            skill_store=self.mock_skill_store,
            agent_id="test_agent"
        )
        
        self.assertEqual(tool.api_key, "test_key")
        self.assertEqual(tool.agent_id, "test_agent")
        self.assertEqual(tool.skill_store, self.mock_skill_store)
        self.assertEqual(tool.category, "wallet")
    
    def test_get_chain_name(self):
        """Test chain name conversion."""
        class TestTool(WalletBaseTool):
            async def _arun(self, *args, **kwargs):
                return "test"
        
        tool = TestTool(
            name="test_tool",
            description="Test tool",
            args_schema=MagicMock(),
            api_key="test_key",
            skill_store=self.mock_skill_store,
            agent_id="test_agent"
        )
        
        # Test with known chain IDs
        self.assertEqual(tool._get_chain_name(1), "eth")
        self.assertEqual(tool._get_chain_name(56), "bsc")
        self.assertEqual(tool._get_chain_name(137), "polygon")
        
        # Test with unknown chain ID
        self.assertEqual(tool._get_chain_name(999999), "eth")


class TestAPIFunctions(unittest.IsolatedAsyncioTestCase):
    """Test the API interaction functions."""
    
    async def test_fetch_moralis_data(self):
        """Test the base Moralis API function."""
        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.get.return_value = DummyResponse(
                200, {"success": True, "data": "test_data"}
            )
            MockClient.return_value.__aenter__.return_value = client_instance
            
            result = await fetch_moralis_data(
                "test_api_key", "test_endpoint", "0xAddress", 1
            )
            
            self.assertEqual(result, {"success": True, "data": "test_data"})
            
            # Test error handling
            client_instance.get.return_value = DummyResponse(404, None)
            client_instance.get.return_value.raise_for_status = AsyncMock(
                side_effect=Exception("HTTP error 404")
            )
            
            result = await fetch_moralis_data(
                "test_api_key", "test_endpoint", "0xAddress", 1
            )
            self.assertIn("error", result)
    
    async def test_fetch_wallet_balances(self):
        """Test fetching wallet balances."""
        with patch("skills.wallet.api.fetch_moralis_data") as mock_fetch:
            mock_fetch.return_value = {
                "result": [{"token_address": "0x123", "symbol": "TEST", "balance": "1000000", "usd_value": 100}]
            }
            
            result = await fetch_wallet_balances("test_api_key", "0xAddress", 1)
            
            self.assertEqual(result["result"][0]["symbol"], "TEST")
            mock_fetch.assert_called_once_with(
                "test_api_key", "wallets/{address}/tokens", "0xAddress", 1, None
            )
    
    async def test_get_solana_portfolio(self):
        """Test getting Solana portfolio."""
        with patch("skills.wallet.api.fetch_solana_api") as mock_fetch:
            mock_fetch.return_value = {
                "nativeBalance": {"solana": 1.5, "lamports": 1500000000},
                "tokens": [
                    {
                        "symbol": "TEST",
                        "name": "Test Token",
                        "mint": "TokenMintAddress",
                        "associatedTokenAddress": "AssocTokenAddress",
                        "amount": 10,
                        "decimals": 9,
                        "amountRaw": "10000000000"
                    }
                ]
            }
            
            result = await get_solana_portfolio("test_api_key", "SolAddress", "mainnet")
            
            mock_fetch.assert_called_once_with(
                "test_api_key", f"/account/mainnet/SolAddress/portfolio"
            )
            self.assertEqual(result["nativeBalance"]["solana"], 1.5)
            self.assertEqual(len(result["tokens"]), 1)
            self.assertEqual(result["tokens"][0]["symbol"], "TEST")


class TestFetchWalletPortfolio(unittest.IsolatedAsyncioTestCase):
    """Test the FetchWalletPortfolio skill."""
    
    async def test_wallet_portfolio_success(self):
        """Test successful wallet portfolio fetch."""
        mock_skill_store = MagicMock()
        
        with patch("skills.wallet.fetch_wallet_portfolio.fetch_wallet_balances") as mock_balances, \
             patch("skills.wallet.fetch_wallet_portfolio.fetch_net_worth") as mock_net_worth:
            
            # Mock successful responses
            mock_balances.return_value = {
                "result": [
                    {
                        "token_address": "0x123",
                        "symbol": "TEST",
                        "name": "Test Token",
                        "balance": "1000000000000000000",
                        "balance_formatted": "1.0",
                        "usd_value": 100
                    }
                ]
            }
            mock_net_worth.return_value = {
                "result": {"total_networth_usd": 1000}
            }
            
            tool = FetchWalletPortfolio(
                name="fetch_wallet_portfolio",
                description="Test description",
                args_schema=MagicMock(),
                api_key="test_key",
                skill_store=mock_skill_store,
                agent_id="test_agent"
            )
            
            result = await tool._arun(address="0xAddress")
            
            self.assertEqual(result.address, "0xAddress")
            self.assertEqual(result.total_net_worth, 1000)
            self.assertEqual(len(result.tokens), 1)
            self.assertEqual(result.tokens[0].symbol, "TEST")
    
    async def test_wallet_portfolio_with_solana(self):
        """Test wallet portfolio with Solana support."""
        mock_skill_store = MagicMock()
        
        with patch("skills.wallet.fetch_wallet_portfolio.fetch_wallet_balances") as mock_evm_balances, \
             patch("skills.wallet.fetch_wallet_portfolio.fetch_net_worth") as mock_net_worth, \
             patch("skills.wallet.fetch_wallet_portfolio.get_solana_portfolio") as mock_sol_portfolio, \
             patch("skills.wallet.fetch_wallet_portfolio.get_token_price") as mock_token_price:
            
            # Mock EVM responses
            mock_evm_balances.return_value = {
                "result": [
                    {
                        "token_address": "0x123",
                        "symbol": "ETH",
                        "name": "Ethereum",
                        "balance": "1000000000000000000",
                        "balance_formatted": "1.0",
                        "usd_value": 2000
                    }
                ]
            }
            mock_net_worth.return_value = {
                "result": {"total_networth_usd": 3000}
            }
            
            # Mock Solana responses
            mock_sol_portfolio.return_value = {
                "nativeBalance": {"solana": 2.0, "lamports": 2000000000},
                "tokens": [
                    {
                        "symbol": "SOL",
                        "name": "Solana",
                        "mint": "So11111111111111111111111111111111111111112",
                        "associatedTokenAddress": "AssocTokenAddress",
                        "amount": 2.0,
                        "decimals": 9,
                        "amountRaw": "2000000000"
                    }
                ]
            }
            
            mock_token_price.return_value = {
                "usdPrice": 500
            }
            
            tool = FetchWalletPortfolio(
                name="fetch_wallet_portfolio",
                description="Test description",
                args_schema=MagicMock(),
                api_key="test_key",
                skill_store=mock_skill_store,
                agent_id="test_agent"
            )
            
            result = await tool._arun(
                address="0xAddress", 
                include_solana=True
            )
            
            self.assertEqual(result.address, "0xAddress")
            self.assertEqual(result.total_net_worth, 3000)  # Using the net worth from mock
            self.assertIn("eth", result.chains)
            self.assertIn("solana", result.chains)
            
            # Check that we have both EVM and Solana tokens
            token_symbols = [token.symbol for token in result.tokens]
            self.assertIn("ETH", token_symbols)
            self.assertIn("SOL", token_symbols)


class TestFetchSolanaPortfolio(unittest.IsolatedAsyncioTestCase):
    """Test the FetchSolanaPortfolio skill."""
    
    async def test_solana_portfolio_success(self):
        """Test successful Solana portfolio fetch."""
        mock_skill_store = MagicMock()
        
        with patch("skills.wallet.fetch_solana_portfolio.get_solana_portfolio") as mock_portfolio, \
             patch("skills.wallet.fetch_solana_portfolio.get_solana_nfts") as mock_nfts, \
             patch("skills.wallet.fetch_solana_portfolio.get_token_price") as mock_token_price:
            
            # Mock successful responses
            mock_portfolio.return_value = {
                "nativeBalance": {"solana": 1.5, "lamports": 1500000000},
                "tokens": [
                    {
                        "symbol": "TEST",
                        "name": "Test Token",
                        "mint": "TokenMintAddress",
                        "associatedTokenAddress": "AssocTokenAddress",
                        "amount": 10,
                        "decimals": 9,
                        "amountRaw": "10000000000"
                    }
                ]
            }
            
            mock_nfts.return_value = [
                {
                    "mint": "NFTMintAddress",
                    "name": "Test NFT",
                    "symbol": "TNFT",
                    "associatedTokenAddress": "AssocTokenAddress",
                    "metadata": {"name": "Test NFT", "image": "image.png"}
                }
            ]
            
            mock_token_price.return_value = {
                "usdPrice": 25
            }
            
            tool = FetchSolanaPortfolio(
                name="fetch_solana_portfolio",
                description="Test description",
                args_schema=MagicMock(),
                api_key="test_key",
                skill_store=mock_skill_store,
                agent_id="test_agent"
            )
            
            result = await tool._arun(
                address="SolanaAddress", 
                include_nfts=True
            )
            
            self.assertEqual(result.address, "SolanaAddress")
            self.assertEqual(result.sol_balance, 1.5)
            self.assertEqual(len(result.tokens), 1)
            self.assertEqual(result.tokens[0].token_info.symbol, "TEST")
            self.assertEqual(len(result.nfts), 1)
            self.assertEqual(result.nfts[0].name, "Test NFT")
            self.assertEqual(result.sol_price_usd, 25)
            self.assertEqual(result.sol_value_usd, 37.5)  # 1.5 SOL * $25


class TestFetchChainPortfolio(unittest.IsolatedAsyncioTestCase):
    """Test the FetchChainPortfolio skill."""
    
    async def test_chain_portfolio_success(self):
        """Test successful chain portfolio fetch."""
        mock_skill_store = MagicMock()
        
        with patch("skills.wallet.fetch_chain_portfolio.fetch_wallet_balances") as mock_balances:
            
            # Mock successful responses
            mock_balances.return_value = {
                "result": [
                    {
                        "token_address": "0x123",
                        "symbol": "ETH",
                        "name": "Ethereum",
                        "logo": "logo.png",
                        "decimals": 18,
                        "balance": "1000000000000000000",
                        "balance_formatted": "1.0",
                        "usd_value": 2000,
                        "native_token": true
                    },
                    {
                        "token_address": "0x456",
                        "symbol": "TOKEN",
                        "name": "Test Token",
                        "logo": "logo2.png",
                        "decimals": 18,
                        "balance": "2000000000000000000",
                        "balance_formatted": "2.0",
                        "usd_value": 200,
                        "native_token": false
                    }
                ]
            }
            
            tool = FetchChainPortfolio(
                name="fetch_chain_portfolio",
                description="Test description",
                args_schema=MagicMock(),
                api_key="test_key",
                skill_store=mock_skill_store,
                agent_id="test_agent"
            )
            
            result = await tool._arun(address="0xAddress", chain_id=1)
            
            self.assertEqual(result.address, "0xAddress")
            self.assertEqual(result.chain_id, 1)
            self.assertEqual(result.chain_name, "eth")
            self.assertEqual(result.total_usd_value, 2200)  # 2000 + 200
            self.assertEqual(len(result.tokens), 1)  # Regular tokens, not native
            self.assertIsNotNone(result.native_token)
            self.assertEqual(result.native_token.symbol, "ETH")
            self.assertEqual(result.tokens[0].symbol, "TOKEN")


class TestSkillInitialization(unittest.TestCase):
    """Test skill initialization and configuration."""
    
    def setUp(self):
        self.mock_skill_store = MagicMock()
        self.mock_agent_store = MagicMock()
        self.mock_chain_provider = MagicMock()
    
    def test_get_wallet_skill(self):
        """Test getting individual skills by name."""
        skill_names = [
            "fetch_wallet_portfolio",
            "fetch_chain_portfolio", 
            "fetch_nft_portfolio",
            "fetch_transaction_history",
            "fetch_solana_portfolio"
        ]
        
        for name in skill_names:
            skill = get_wallet_skill(
                name,
                "test_api_key",
                self.mock_skill_store,
                "test_agent",
                self.mock_agent_store,
                self.mock_chain_provider
            )
            
            self.assertIsNotNone(skill)
            self.assertEqual(skill.api_key, "test_api_key")
            
            # Check the correct class is instantiated
            if name == "fetch_wallet_portfolio":
                self.assertIsInstance(skill, FetchWalletPortfolio)
            elif name == "fetch_chain_portfolio":
                self.assertIsInstance(skill, FetchChainPortfolio)
            elif name == "fetch_nft_portfolio":
                self.assertIsInstance(skill, FetchNftPortfolio)
            elif name == "fetch_transaction_history":
                self.assertIsInstance(skill, FetchTransactionHistory)
            elif name == "fetch_solana_portfolio":
                self.assertIsInstance(skill, FetchSolanaPortfolio)
    
    def test_invalid_skill_name(self):
        """Test error handling for invalid skill names."""
        with self.assertRaises(ValueError):
            get_wallet_skill(
                "invalid_skill",
                "test_api_key",
                self.mock_skill_store,
                "test_agent",
                self.mock_agent_store
            )
    
    def test_get_skills(self):
        """Test getting multiple skills from config."""
        config = {
            "api_key": "test_api_key",
            "states": {
                "fetch_wallet_portfolio": "public",
                "fetch_chain_portfolio": "public",
                "fetch_nft_portfolio": "private",
                "fetch_transaction_history": "private",
                "fetch_solana_portfolio": "public"
            },
            "supported_chains": {"evm": True, "solana": True}
        }
        
        # Test public skills
        with patch("skills.wallet.get_wallet_skill") as mock_get_skill:
            mock_get_skill.side_effect = lambda name, *args, **kwargs: name
            
            public_skills = get_skills(
                config,
                False,  # is_private=False
                self.mock_skill_store,
                "test_agent",
                self.mock_agent_store,
                self.mock_chain_provider
            )
            
            self.assertEqual(len(public_skills), 3)
            self.assertIn("fetch_wallet_portfolio", public_skills)
            self.assertIn("fetch_chain_portfolio", public_skills)
            self.assertIn("fetch_solana_portfolio", public_skills)
            
            # Test all skills (public + private)
            all_skills = get_skills(
                config,
                True,  # is_private=True
                self.mock_skill_store,
                "test_agent",
                self.mock_agent_store,
                self.mock_chain_provider
            )
            
            self.assertEqual(len(all_skills), 5)
            self.assertIn("fetch_wallet_portfolio", all_skills)
            self.assertIn("fetch_chain_portfolio", all_skills)
            self.assertIn("fetch_nft_portfolio", all_skills)
            self.assertIn("fetch_transaction_history", all_skills)
            self.assertIn("fetch_solana_portfolio", all_skills)
    
    def test_chain_support_configuration(self):
        """Test chain support configuration."""
        config = {
            "api_key": "test_api_key",
            "states": {
                "fetch_wallet_portfolio": "public",
                "fetch_chain_portfolio": "public",
                "fetch_nft_portfolio": "public",
                "fetch_transaction_history": "public",
                "fetch_solana_portfolio": "public"
            },
            "supported_chains": {"evm": True, "solana": False}  # Solana disabled
        }
        
        # Test that Solana skills are not included when Solana is disabled
        with patch("skills.wallet.get_wallet_skill") as mock_get_skill:
            mock_get_skill.side_effect = lambda name, *args, **kwargs: name
            
            skills = get_skills(
                config,
                False,
                self.mock_skill_store,
                "test_agent",
                self.mock_agent_store,
                self.mock_chain_provider
            )
            
            self.assertEqual(len(skills), 4)
            self.assertIn("fetch_wallet_portfolio", skills)
            self.assertIn("fetch_chain_portfolio", skills)
            self.assertIn("fetch_nft_portfolio", skills)
            self.assertIn("fetch_transaction_history", skills)
            self.assertNotIn("fetch_solana_portfolio", skills)


class TestIntegration(unittest.TestCase):
    """Integration tests for wallet skills."""
    
    def test_wallet_skill_configuration(self):
        """Test wallet skill configuration in agent config."""
        # Example agent configuration
        agent_config = {
            "id": "crypto-agent",
            "skills": {
                "wallet": {
                    "api_key": "test_api_key",
                    "states": {
                        "fetch_wallet_portfolio": "public",
                        "fetch_chain_portfolio": "public",
                        "fetch_nft_portfolio": "private",
                        "fetch_transaction_history": "private",
                        "fetch_solana_portfolio": "public"
                    },
                    "supported_chains": {
                        "evm": True,
                        "solana": True
                    }
                }
            }
        }
        
        # Verify the configuration structure is valid
        wallet_config = agent_config["skills"]["wallet"]
        self.assertIn("api_key", wallet_config)
        self.assertIn("states", wallet_config)
        self.assertIn("supported_chains", wallet_config)
        
        # Check that all required skills are configured
        states = wallet_config["states"]
        required_skills = [
            "fetch_wallet_portfolio",
            "fetch_chain_portfolio",
            "fetch_nft_portfolio",
            "fetch_transaction_history",
            "fetch_solana_portfolio"
        ]
        
        for skill in required_skills:
            self.assertIn(skill, states)
            self.assertIn(states[skill], ["public", "private", "disabled"])
        
        # Check chain configuration
        chains = wallet_config["supported_chains"]
        self.assertIn("evm", chains)
        self.assertIn("solana", chains)
        self.assertTrue(isinstance(chains["evm"], bool))
        self.assertTrue(isinstance(chains["solana"], bool))


if __name__ == "__main__":
    unittest.main()