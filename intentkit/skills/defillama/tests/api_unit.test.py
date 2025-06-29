import unittest
from unittest.mock import AsyncMock, patch

# Import the endpoints from your module.
# Adjust the import path if your module has a different name or location.
from intentkit.skills.defillama.api import (
    fetch_batch_historical_prices,
    fetch_block,
    fetch_chain_historical_tvl,
    fetch_chains,
    fetch_current_prices,
    # Volume related functions
    fetch_dex_overview,
    fetch_dex_summary,
    # Fees related functions
    fetch_fees_overview,
    fetch_first_price,
    fetch_historical_prices,
    fetch_historical_tvl,
    fetch_options_overview,
    fetch_pool_chart,
    # Yields related functions
    fetch_pools,
    # Price related functions
    fetch_price_chart,
    fetch_price_percentage,
    fetch_protocol,
    fetch_protocol_current_tvl,
    # Original functions
    fetch_protocols,
    fetch_stablecoin_chains,
    fetch_stablecoin_charts,
    fetch_stablecoin_prices,
    # Stablecoin related functions
    fetch_stablecoins,
)


# Dummy response to simulate httpx responses.
class DummyResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data


class TestDefiLlamaAPI(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # Set up a fixed timestamp that all tests will use
        cls.mock_timestamp = 1677648000  # Fixed timestamp

    async def asyncSetUp(self):
        # Start the patcher before each test
        self.datetime_patcher = patch("skills.defillama.api.datetime")
        self.mock_datetime = self.datetime_patcher.start()
        # Configure the mock to return our fixed timestamp
        self.mock_datetime.now.return_value.timestamp.return_value = self.mock_timestamp

    async def asyncTearDown(self):
        # Stop the patcher after each test
        self.datetime_patcher.stop()

    # Helper method to patch httpx.AsyncClient and set up the dummy client.
    async def _run_with_dummy(
        self, func, expected_url, dummy_response, *args, expected_kwargs=None
    ):
        if expected_kwargs is None:
            expected_kwargs = {}
        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.get.return_value = dummy_response
            # Ensure that __aenter__ returns our dummy client.
            MockClient.return_value.__aenter__.return_value = client_instance
            result = await func(*args)
            # Check that the get call was made with the expected URL (and parameters, if any).
            client_instance.get.assert_called_once_with(expected_url, **expected_kwargs)
            return result

    # --- Tests for fetch_protocols ---
    async def test_fetch_protocols_success(self):
        dummy = DummyResponse(200, {"protocols": []})
        result = await self._run_with_dummy(
            fetch_protocols,
            "https://api.llama.fi/protocols",
            dummy,
        )
        self.assertEqual(result, {"protocols": []})

    async def test_fetch_protocols_error(self):
        dummy = DummyResponse(404, None)
        result = await self._run_with_dummy(
            fetch_protocols,
            "https://api.llama.fi/protocols",
            dummy,
        )
        self.assertEqual(result, {"error": "API returned status code 404"})

    # --- Tests for fetch_protocol ---
    async def test_fetch_protocol_success(self):
        protocol = "testprotocol"
        dummy = DummyResponse(200, {"protocol": protocol})
        expected_url = f"https://api.llama.fi/protocol/{protocol}"
        result = await self._run_with_dummy(
            fetch_protocol, expected_url, dummy, protocol
        )
        self.assertEqual(result, {"protocol": protocol})

    async def test_fetch_protocol_error(self):
        protocol = "testprotocol"
        dummy = DummyResponse(500, None)
        expected_url = f"https://api.llama.fi/protocol/{protocol}"
        result = await self._run_with_dummy(
            fetch_protocol, expected_url, dummy, protocol
        )
        self.assertEqual(result, {"error": "API returned status code 500"})

    # --- Tests for fetch_historical_tvl ---
    async def test_fetch_historical_tvl_success(self):
        dummy = DummyResponse(200, {"historical": "data"})
        expected_url = "https://api.llama.fi/v2/historicalChainTvl"
        result = await self._run_with_dummy(
            fetch_historical_tvl,
            expected_url,
            dummy,
        )
        self.assertEqual(result, {"historical": "data"})

    async def test_fetch_historical_tvl_error(self):
        dummy = DummyResponse(400, None)
        expected_url = "https://api.llama.fi/v2/historicalChainTvl"
        result = await self._run_with_dummy(
            fetch_historical_tvl,
            expected_url,
            dummy,
        )
        self.assertEqual(result, {"error": "API returned status code 400"})

    # --- Tests for fetch_chain_historical_tvl ---
    async def test_fetch_chain_historical_tvl_success(self):
        chain = "ethereum"
        dummy = DummyResponse(200, {"chain": chain})
        expected_url = f"https://api.llama.fi/v2/historicalChainTvl/{chain}"
        result = await self._run_with_dummy(
            fetch_chain_historical_tvl, expected_url, dummy, chain
        )
        self.assertEqual(result, {"chain": chain})

    async def test_fetch_chain_historical_tvl_error(self):
        chain = "ethereum"
        dummy = DummyResponse(503, None)
        expected_url = f"https://api.llama.fi/v2/historicalChainTvl/{chain}"
        result = await self._run_with_dummy(
            fetch_chain_historical_tvl, expected_url, dummy, chain
        )
        self.assertEqual(result, {"error": "API returned status code 503"})

    # --- Tests for fetch_protocol_current_tvl ---
    async def test_fetch_protocol_current_tvl_success(self):
        protocol = "testprotocol"
        dummy = DummyResponse(200, {"current_tvl": 12345})
        expected_url = f"https://api.llama.fi/tvl/{protocol}"
        result = await self._run_with_dummy(
            fetch_protocol_current_tvl, expected_url, dummy, protocol
        )
        self.assertEqual(result, {"current_tvl": 12345})

    async def test_fetch_protocol_current_tvl_error(self):
        protocol = "testprotocol"
        dummy = DummyResponse(418, None)
        expected_url = f"https://api.llama.fi/tvl/{protocol}"
        result = await self._run_with_dummy(
            fetch_protocol_current_tvl, expected_url, dummy, protocol
        )
        self.assertEqual(result, {"error": "API returned status code 418"})

    # --- Tests for fetch_chains ---
    async def test_fetch_chains_success(self):
        dummy = DummyResponse(200, {"chains": ["eth", "bsc"]})
        expected_url = "https://api.llama.fi/v2/chains"
        result = await self._run_with_dummy(
            fetch_chains,
            expected_url,
            dummy,
        )
        self.assertEqual(result, {"chains": ["eth", "bsc"]})

    async def test_fetch_chains_error(self):
        dummy = DummyResponse(404, None)
        expected_url = "https://api.llama.fi/v2/chains"
        result = await self._run_with_dummy(
            fetch_chains,
            expected_url,
            dummy,
        )
        self.assertEqual(result, {"error": "API returned status code 404"})

    # --- Tests for fetch_current_prices ---
    async def test_fetch_current_prices_success(self):
        coins = ["coin1", "coin2"]
        coins_str = ",".join(coins)
        dummy = DummyResponse(200, {"prices": "data"})
        expected_url = f"https://api.llama.fi/prices/current/{coins_str}?searchWidth=4h"
        result = await self._run_with_dummy(
            fetch_current_prices, expected_url, dummy, coins
        )
        self.assertEqual(result, {"prices": "data"})

    async def test_fetch_current_prices_error(self):
        coins = ["coin1", "coin2"]
        coins_str = ",".join(coins)
        dummy = DummyResponse(500, None)
        expected_url = f"https://api.llama.fi/prices/current/{coins_str}?searchWidth=4h"
        result = await self._run_with_dummy(
            fetch_current_prices, expected_url, dummy, coins
        )
        self.assertEqual(result, {"error": "API returned status code 500"})

    # --- Tests for fetch_historical_prices ---
    async def test_fetch_historical_prices_success(self):
        timestamp = 1609459200
        coins = ["coin1", "coin2"]
        coins_str = ",".join(coins)
        dummy = DummyResponse(200, {"historical_prices": "data"})
        expected_url = f"https://api.llama.fi/prices/historical/{timestamp}/{coins_str}?searchWidth=4h"
        result = await self._run_with_dummy(
            fetch_historical_prices, expected_url, dummy, timestamp, coins
        )
        self.assertEqual(result, {"historical_prices": "data"})

    async def test_fetch_historical_prices_error(self):
        timestamp = 1609459200
        coins = ["coin1", "coin2"]
        coins_str = ",".join(coins)
        dummy = DummyResponse(400, None)
        expected_url = f"https://api.llama.fi/prices/historical/{timestamp}/{coins_str}?searchWidth=4h"
        result = await self._run_with_dummy(
            fetch_historical_prices, expected_url, dummy, timestamp, coins
        )
        self.assertEqual(result, {"error": "API returned status code 400"})

    # --- Tests for fetch_batch_historical_prices ---
    async def test_fetch_batch_historical_prices_success(self):
        coins_timestamps = {"coin1": [1609459200, 1609545600], "coin2": [1609459200]}
        dummy = DummyResponse(200, {"batch": "data"})
        expected_url = "https://api.llama.fi/batchHistorical"
        # For this endpoint, a params dict is sent.
        expected_params = {"coins": coins_timestamps, "searchWidth": "600"}
        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.get.return_value = dummy
            MockClient.return_value.__aenter__.return_value = client_instance
            result = await fetch_batch_historical_prices(coins_timestamps)
            client_instance.get.assert_called_once_with(
                expected_url, params=expected_params
            )
            self.assertEqual(result, {"batch": "data"})

    async def test_fetch_batch_historical_prices_error(self):
        coins_timestamps = {"coin1": [1609459200], "coin2": [1609459200]}
        dummy = DummyResponse(503, None)
        expected_url = "https://api.llama.fi/batchHistorical"
        expected_params = {"coins": coins_timestamps, "searchWidth": "600"}
        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.get.return_value = dummy
            MockClient.return_value.__aenter__.return_value = client_instance
            result = await fetch_batch_historical_prices(coins_timestamps)
            client_instance.get.assert_called_once_with(
                expected_url, params=expected_params
            )
            self.assertEqual(result, {"error": "API returned status code 503"})

    async def test_fetch_price_chart_success(self):
        coins = ["bitcoin", "ethereum"]
        coins_str = ",".join(coins)
        dummy = DummyResponse(200, {"chart": "data"})
        expected_url = f"https://api.llama.fi/chart/{coins_str}"

        # Calculate start time based on mock timestamp
        start_time = self.mock_timestamp - 86400  # mock timestamp - 1 day
        expected_params = {
            "start": start_time,
            "span": 10,
            "period": "2d",
            "searchWidth": "600",
        }

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.get.return_value = dummy
            MockClient.return_value.__aenter__.return_value = client_instance
            result = await fetch_price_chart(coins)
            client_instance.get.assert_called_once_with(
                expected_url, params=expected_params
            )
            self.assertEqual(result, {"chart": "data"})

    async def test_fetch_price_chart_error(self):
        coins = ["bitcoin", "ethereum"]
        coins_str = ",".join(coins)
        dummy = DummyResponse(500, None)
        expected_url = f"https://api.llama.fi/chart/{coins_str}"

        # Calculate start time based on mock timestamp
        start_time = self.mock_timestamp - 86400  # mock timestamp - 1 day
        expected_params = {
            "start": start_time,
            "span": 10,
            "period": "2d",
            "searchWidth": "600",
        }

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.get.return_value = dummy
            MockClient.return_value.__aenter__.return_value = client_instance
            result = await fetch_price_chart(coins)
            client_instance.get.assert_called_once_with(
                expected_url, params=expected_params
            )
            self.assertEqual(result, {"error": "API returned status code 500"})

    # --- Tests for fetch_price_percentage ---
    async def test_fetch_price_percentage_success(self):
        coins = ["bitcoin", "ethereum"]
        coins_str = ",".join(coins)
        dummy = DummyResponse(200, {"percentage": "data"})
        expected_url = f"https://api.llama.fi/percentage/{coins_str}"

        mock_timestamp = 1677648000  # Fixed timestamp
        with patch("skills.defillama.api.datetime") as mock_datetime:
            mock_datetime.now.return_value.timestamp.return_value = mock_timestamp
            expected_params = {
                "timestamp": mock_timestamp,
                "lookForward": "false",
                "period": "24h",
            }

            with patch("httpx.AsyncClient") as MockClient:
                client_instance = AsyncMock()
                client_instance.get.return_value = dummy
                MockClient.return_value.__aenter__.return_value = client_instance
                result = await fetch_price_percentage(coins)
                client_instance.get.assert_called_once_with(
                    expected_url, params=expected_params
                )
                self.assertEqual(result, {"percentage": "data"})

    async def test_fetch_price_percentage_error(self):
        coins = ["bitcoin", "ethereum"]
        coins_str = ",".join(coins)
        dummy = DummyResponse(404, None)
        expected_url = f"https://api.llama.fi/percentage/{coins_str}"

        expected_params = {
            "timestamp": self.mock_timestamp,
            "lookForward": "false",
            "period": "24h",
        }

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.get.return_value = dummy
            MockClient.return_value.__aenter__.return_value = client_instance
            result = await fetch_price_percentage(coins)
            client_instance.get.assert_called_once_with(
                expected_url, params=expected_params
            )
            self.assertEqual(result, {"error": "API returned status code 404"})

    async def test_fetch_price_percentage_error2(self):
        coins = ["bitcoin", "ethereum"]
        coins_str = ",".join(coins)
        dummy = DummyResponse(404, None)
        expected_url = f"https://api.llama.fi/percentage/{coins_str}"

        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value.timestamp.return_value = 1677648000
            expected_params = {
                "timestamp": 1677648000,
                "lookForward": "false",
                "period": "24h",
            }

            with patch("httpx.AsyncClient") as MockClient:
                client_instance = AsyncMock()
                client_instance.get.return_value = dummy
                MockClient.return_value.__aenter__.return_value = client_instance
                result = await fetch_price_percentage(coins)
                client_instance.get.assert_called_once_with(
                    expected_url, params=expected_params
                )
                self.assertEqual(result, {"error": "API returned status code 404"})

    # --- Tests for fetch_first_price ---
    async def test_fetch_first_price_success(self):
        coins = ["bitcoin", "ethereum"]
        coins_str = ",".join(coins)
        dummy = DummyResponse(200, {"first_prices": "data"})
        expected_url = f"https://api.llama.fi/prices/first/{coins_str}"
        result = await self._run_with_dummy(
            fetch_first_price, expected_url, dummy, coins
        )
        self.assertEqual(result, {"first_prices": "data"})

    async def test_fetch_first_price_error(self):
        coins = ["bitcoin", "ethereum"]
        coins_str = ",".join(coins)
        dummy = DummyResponse(500, None)
        expected_url = f"https://api.llama.fi/prices/first/{coins_str}"
        result = await self._run_with_dummy(
            fetch_first_price, expected_url, dummy, coins
        )
        self.assertEqual(result, {"error": "API returned status code 500"})

    # --- Tests for fetch_block ---
    async def test_fetch_block_success(self):
        chain = "ethereum"
        dummy = DummyResponse(200, {"block": 123456})
        mock_timestamp = 1677648000  # Fixed timestamp

        with patch("skills.defillama.api.datetime") as mock_datetime:
            mock_datetime.now.return_value.timestamp.return_value = mock_timestamp
            expected_url = f"https://api.llama.fi/block/{chain}/{mock_timestamp}"
            result = await self._run_with_dummy(fetch_block, expected_url, dummy, chain)
            self.assertEqual(result, {"block": 123456})

    async def test_fetch_block_error(self):
        chain = "ethereum"
        dummy = DummyResponse(404, None)
        mock_timestamp = 1677648000  # Fixed timestamp

        with patch("skills.defillama.api.datetime") as mock_datetime:
            mock_datetime.now.return_value.timestamp.return_value = mock_timestamp
            expected_url = f"https://api.llama.fi/block/{chain}/{mock_timestamp}"
            result = await self._run_with_dummy(fetch_block, expected_url, dummy, chain)
            self.assertEqual(result, {"error": "API returned status code 404"})

    # --- Tests for Stablecoins API ---
    async def test_fetch_stablecoins_success(self):
        dummy = DummyResponse(200, {"stablecoins": "data"})
        expected_url = "https://api.llama.fi/stablecoins"
        expected_params = {"includePrices": "true"}

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.get.return_value = dummy
            MockClient.return_value.__aenter__.return_value = client_instance
            result = await fetch_stablecoins()
            client_instance.get.assert_called_once_with(
                expected_url, params=expected_params
            )
            self.assertEqual(result, {"stablecoins": "data"})

    async def test_fetch_stablecoin_charts_success(self):
        stablecoin_id = "USDT"
        chain = "ethereum"
        dummy = DummyResponse(200, {"charts": "data"})
        expected_url = (
            f"https://api.llama.fi/stablecoincharts/{chain}?stablecoin={stablecoin_id}"
        )
        result = await self._run_with_dummy(
            fetch_stablecoin_charts, expected_url, dummy, stablecoin_id, chain
        )
        self.assertEqual(result, {"charts": "data"})

    async def test_fetch_stablecoin_chains_success(self):
        dummy = DummyResponse(200, {"chains": "data"})
        expected_url = "https://api.llama.fi/stablecoinchains"
        result = await self._run_with_dummy(
            fetch_stablecoin_chains, expected_url, dummy
        )
        self.assertEqual(result, {"chains": "data"})

    async def test_fetch_stablecoin_prices_success(self):
        dummy = DummyResponse(200, {"prices": "data"})
        expected_url = "https://api.llama.fi/stablecoinprices"
        result = await self._run_with_dummy(
            fetch_stablecoin_prices, expected_url, dummy
        )
        self.assertEqual(result, {"prices": "data"})

    # --- Tests for Yields API ---
    async def test_fetch_pools_success(self):
        dummy = DummyResponse(200, {"pools": "data"})
        expected_url = "https://api.llama.fi/pools"
        result = await self._run_with_dummy(fetch_pools, expected_url, dummy)
        self.assertEqual(result, {"pools": "data"})

    async def test_fetch_pool_chart_success(self):
        pool_id = "compound-usdc"
        dummy = DummyResponse(200, {"chart": "data"})
        expected_url = f"https://api.llama.fi/chart/{pool_id}"
        result = await self._run_with_dummy(
            fetch_pool_chart, expected_url, dummy, pool_id
        )
        self.assertEqual(result, {"chart": "data"})

    # --- Tests for Volumes API ---
    async def test_fetch_dex_overview_success(self):
        dummy = DummyResponse(200, {"overview": "data"})
        expected_url = "https://api.llama.fi/overview/dexs"
        expected_params = {
            "excludeTotalDataChart": "true",
            "excludeTotalDataChartBreakdown": "true",
            "dataType": "dailyVolume",
        }

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.get.return_value = dummy
            MockClient.return_value.__aenter__.return_value = client_instance
            result = await fetch_dex_overview()
            client_instance.get.assert_called_once_with(
                expected_url, params=expected_params
            )
            self.assertEqual(result, {"overview": "data"})

    async def test_fetch_dex_summary_success(self):
        protocol = "uniswap"
        dummy = DummyResponse(200, {"summary": "data"})
        expected_url = f"https://api.llama.fi/summary/dexs/{protocol}"
        expected_params = {
            "excludeTotalDataChart": "true",
            "excludeTotalDataChartBreakdown": "true",
            "dataType": "dailyVolume",
        }

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.get.return_value = dummy
            MockClient.return_value.__aenter__.return_value = client_instance
            result = await fetch_dex_summary(protocol)
            client_instance.get.assert_called_once_with(
                expected_url, params=expected_params
            )
            self.assertEqual(result, {"summary": "data"})

    async def test_fetch_options_overview_success(self):
        dummy = DummyResponse(200, {"options": "data"})
        expected_url = "https://api.llama.fi/overview/options"
        expected_params = {
            "excludeTotalDataChart": "true",
            "excludeTotalDataChartBreakdown": "true",
            "dataType": "dailyPremiumVolume",
        }

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.get.return_value = dummy
            MockClient.return_value.__aenter__.return_value = client_instance
            result = await fetch_options_overview()
            client_instance.get.assert_called_once_with(
                expected_url, params=expected_params
            )
            self.assertEqual(result, {"options": "data"})

    # --- Tests for Fees API ---
    async def test_fetch_fees_overview_success(self):
        dummy = DummyResponse(200, {"fees": "data"})
        expected_url = "https://api.llama.fi/overview/fees"
        expected_params = {
            "excludeTotalDataChart": "true",
            "excludeTotalDataChartBreakdown": "true",
            "dataType": "dailyFees",
        }

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.get.return_value = dummy
            MockClient.return_value.__aenter__.return_value = client_instance
            result = await fetch_fees_overview()
            client_instance.get.assert_called_once_with(
                expected_url, params=expected_params
            )
            self.assertEqual(result, {"fees": "data"})


if __name__ == "__main__":
    unittest.main()
