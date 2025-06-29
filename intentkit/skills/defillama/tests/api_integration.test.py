import asyncio
import logging
import unittest
from datetime import datetime, timedelta
from unittest.runner import TextTestResult

# Import all functions from your API module
from intentkit.skills.defillama.api import (
    fetch_chains,
    fetch_current_prices,
    fetch_dex_overview,
    fetch_dex_summary,
    fetch_fees_overview,
    fetch_historical_prices,
    fetch_historical_tvl,
    fetch_price_chart,
    fetch_protocol,
    fetch_protocols,
    fetch_stablecoin_chains,
    fetch_stablecoin_prices,
    fetch_stablecoins,
)

# Configure logging to only show warnings and errors
logging.basicConfig(level=logging.WARNING)


class QuietTestResult(TextTestResult):
    """Custom TestResult class that minimizes output unless there's a failure"""

    def startTest(self, test):
        self._started_at = datetime.now()
        super().startTest(test)

    def addSuccess(self, test):
        super().addSuccess(test)
        if self.showAll:
            self.stream.write("")
            self.stream.flush()

    def addError(self, test, err):
        super().addError(test, err)
        self.stream.write("\n")
        self.stream.write(self.separator1 + "\n")
        self.stream.write(f"ERROR: {self.getDescription(test)}\n")
        self.stream.write(self.separator2 + "\n")
        self.stream.write(self._exc_info_to_string(err, test))
        self.stream.write("\n")
        self.stream.flush()

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.stream.write("\n")
        self.stream.write(self.separator1 + "\n")
        self.stream.write(f"FAIL: {self.getDescription(test)}\n")
        self.stream.write(self.separator2 + "\n")
        self.stream.write(self._exc_info_to_string(err, test))
        self.stream.write("\n")
        self.stream.flush()


class QuietTestRunner(unittest.TextTestRunner):
    """Custom TestRunner that uses QuietTestResult"""

    resultclass = QuietTestResult


class TestDefiLlamaAPI(unittest.TestCase):
    """Integration tests for DeFi Llama API client"""

    def setUp(self):
        """Set up the async event loop"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.timeout = 3000

    def tearDown(self):
        """Clean up the event loop"""
        self.loop.close()

    def run_async(self, coro):
        """Helper to run async functions in test methods with timeout"""
        try:
            return self.loop.run_until_complete(
                asyncio.wait_for(coro, timeout=self.timeout)
            )
        except asyncio.TimeoutError:
            raise AssertionError(f"Test timed out after {self.timeout} seconds")
        except Exception as e:
            raise AssertionError(f"Test failed with exception: {str(e)}")

    def assert_successful_response(self, response):
        """Helper to check if response contains an error"""
        if isinstance(response, dict) and "error" in response:
            raise AssertionError(f"API request failed: {response['error']}")

    def test_tvl_endpoints(self):
        """Test TVL-related endpoints"""
        # Test fetch_protocols
        protocols = self.run_async(fetch_protocols())
        self.assert_successful_response(protocols)
        self.assertIsInstance(protocols, list)
        if len(protocols) > 0:
            self.assertIn("tvl", protocols[0])

        # Test fetch_protocol using Aave as an example
        protocol_data = self.run_async(fetch_protocol("aave"))
        self.assert_successful_response(protocol_data)
        self.assertIsInstance(protocol_data, dict)

        # Test fetch_historical_tvl
        historical_tvl = self.run_async(fetch_historical_tvl())
        self.assert_successful_response(historical_tvl)
        self.assertIsInstance(historical_tvl, list)
        # Verify the structure of historical TVL data points
        if len(historical_tvl) > 0:
            self.assertIn("date", historical_tvl[0])
            self.assertIn("tvl", historical_tvl[0])

        # Test fetch_chains
        chains = self.run_async(fetch_chains())
        self.assert_successful_response(chains)
        self.assertIsInstance(chains, list)

    def test_coins_endpoints(self):
        """Test coin price-related endpoints"""
        test_coins = ["ethereum:0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"]

        # Test fetch_current_prices
        current_prices = self.run_async(fetch_current_prices(test_coins))
        self.assert_successful_response(current_prices)
        self.assertIsInstance(current_prices, dict)

        # Test fetch_historical_prices
        timestamp = int((datetime.now() - timedelta(days=1)).timestamp())
        historical_prices = self.run_async(
            fetch_historical_prices(timestamp, test_coins)
        )
        self.assert_successful_response(historical_prices)
        self.assertIsInstance(historical_prices, dict)

        # Test fetch_price_chart
        price_chart = self.run_async(fetch_price_chart(test_coins))
        self.assert_successful_response(price_chart)
        self.assertIsInstance(price_chart, dict)
        self.assertIn("coins", price_chart)
        # Verify the structure of the response
        coin_data = price_chart["coins"].get(test_coins[0])
        self.assertIsNotNone(coin_data)
        self.assertIn("prices", coin_data)
        self.assertIsInstance(coin_data["prices"], list)

    def test_stablecoin_endpoints(self):
        """Test stablecoin-related endpoints"""
        # Test fetch_stablecoins
        stablecoins = self.run_async(fetch_stablecoins())
        self.assert_successful_response(stablecoins)
        self.assertIsInstance(stablecoins, dict)

        # Test fetch_stablecoin_chains
        chains = self.run_async(fetch_stablecoin_chains())
        self.assert_successful_response(chains)
        self.assertIsInstance(chains, list)

        # Test fetch_stablecoin_prices
        prices = self.run_async(fetch_stablecoin_prices())
        self.assert_successful_response(prices)
        self.assertIsInstance(prices, list)

    def test_volume_endpoints(self):
        """Test volume-related endpoints"""
        # Test fetch_dex_overview
        dex_overview = self.run_async(fetch_dex_overview())
        self.assert_successful_response(dex_overview)
        self.assertIsInstance(dex_overview, dict)

        # Test fetch_dex_summary using Uniswap as example
        dex_summary = self.run_async(fetch_dex_summary("uniswap"))
        self.assert_successful_response(dex_summary)
        self.assertIsInstance(dex_summary, dict)

    def test_fees_endpoint(self):
        """Test fees endpoint"""
        fees_overview = self.run_async(fetch_fees_overview())
        self.assert_successful_response(fees_overview)
        self.assertIsInstance(fees_overview, dict)


if __name__ == "__main__":
    # Use the quiet test runner
    runner = QuietTestRunner(verbosity=1)
    unittest.main(testRunner=runner)
