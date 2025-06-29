from abc import ABC, abstractmethod
from enum import IntEnum, StrEnum

import httpx


class Chain(StrEnum):
    """
    Enum of supported blockchain chains, using QuickNode's naming conventions.

    This list is based on common chain names used by QuickNode, but it's essential
    to consult the official QuickNode documentation for the most accurate and
    up-to-date list of supported chains and their exact names.  Chain names can
    sometimes be slightly different from what you might expect.
    """

    # EVM Chains
    Ethereum = "eth"  # Or "ethereum"
    Avalanche = "avax"  # Or "avalanche"
    Binance = "bsc"  # BNB Smart Chain
    Polygon = "matic"  # Or "polygon"
    Gnosis = "gnosis"  # Or "xdai"
    Celo = "celo"
    Fantom = "fantom"
    Moonbeam = "moonbeam"
    Aurora = "aurora"
    Arbitrum = "arbitrum"
    Optimism = "optimism"
    Linea = "linea"
    ZkSync = "zksync"

    # Base
    Base = "base"

    # Cosmos Ecosystem
    CosmosHub = "cosmos"  # Or "cosmos-hub"
    Osmosis = "osmosis"
    Juno = "juno"
    Evmos = "evmos"
    Kava = "kava"
    Persistence = "persistence"
    Secret = "secret"
    Stargaze = "stargaze"
    Terra = "terra"  # Or "terra-classic"
    Axelar = "axelar"

    # Solana
    Solana = "sol"  # Or "solana"

    # Other Chains
    Sonic = "sonic"
    Bera = "bera"
    Near = "near"
    Frontera = "frontera"


class Network(StrEnum):
    """
    Enum of well-known blockchain network names, based on QuickNode API.

    This list is not exhaustive and might not be completely up-to-date.
    Always consult the official QuickNode documentation for the most accurate
    and current list of supported networks.  Network names can sometimes
    be slightly different from what you might expect.
    """

    # Ethereum Mainnet and Testnets
    EthereumMainnet = "ethereum-mainnet"
    EthereumGoerli = "ethereum-goerli"  # Goerli Testnet (deprecated, Sepolia preferred)
    EthereumSepolia = "ethereum-sepolia"

    # Layer 2s on Ethereum
    ArbitrumMainnet = "arbitrum-mainnet"
    OptimismMainnet = "optimism-mainnet"  # Or just "optimism"
    LineaMainnet = "linea-mainnet"
    ZkSyncMainnet = "zksync-mainnet"  # zkSync Era

    # Other EVM Chains
    AvalancheMainnet = "avalanche-mainnet"
    BinanceMainnet = "bsc"  # BNB Smart Chain (BSC)
    PolygonMainnet = "matic"  # Or "polygon-mainnet"
    GnosisMainnet = "xdai"  # Or "gnosis"
    CeloMainnet = "celo-mainnet"
    FantomMainnet = "fantom-mainnet"
    MoonbeamMainnet = "moonbeam-mainnet"
    AuroraMainnet = "aurora-mainnet"

    # Base
    BaseMainnet = "base-mainnet"
    BaseSepolia = "base-sepolia"

    # Cosmos Ecosystem (These can be tricky and may need updates)
    CosmosHubMainnet = "cosmos-hub-mainnet"  # Or just "cosmos"
    OsmosisMainnet = "osmosis-mainnet"  # Or just "osmosis"
    JunoMainnet = "juno-mainnet"  # Or just "juno"

    # Solana (Note: Solana uses cluster names, not typical network names)
    SolanaMainnet = "solana-mainnet"  # Or "solana"

    # Other Chains
    SonicMainnet = "sonic-mainnet"
    BeraMainnet = "bera-mainnet"
    NearMainnet = "near-mainnet"  # Or just "near"
    KavaMainnet = "kava-mainnet"  # Or just "kava"
    EvmosMainnet = "evmos-mainnet"  # Or just "evmos"
    PersistenceMainnet = "persistence-mainnet"  # Or just "persistence"
    SecretMainnet = "secret-mainnet"  # Or just "secret"
    StargazeMainnet = "stargaze-mainnet"  # Or just "stargaze"
    TerraMainnet = "terra-mainnet"  # Or "terra-classic"
    AxelarMainnet = "axelar-mainnet"  # Or just "axelar"
    FronteraMainnet = "frontera-mainnet"


class NetworkId(IntEnum):
    """
    Enum of well-known blockchain network IDs.

    This list is not exhaustive and might not be completely up-to-date.
    Always consult the official documentation for the specific blockchain
    you are working with for the most accurate and current chain ID.
    """

    # Ethereum Mainnet and Testnets
    EthereumMainnet = 1
    EthereumGoerli = 5  # Goerli Testnet (deprecated, Sepolia is preferred)
    EthereumSepolia = 11155111

    # Layer 2s on Ethereum
    ArbitrumMainnet = 42161
    OptimismMainnet = 10
    LineaMainnet = 59144
    ZkSyncMainnet = 324  # zkSync Era

    # Other EVM Chains
    AvalancheMainnet = 43114
    BinanceMainnet = 56  # BNB Smart Chain (BSC)
    PolygonMainnet = 137
    GnosisMainnet = 100  # xDai Chain
    CeloMainnet = 42220
    FantomMainnet = 250
    MoonbeamMainnet = 1284
    AuroraMainnet = 1313161554

    # Base
    BaseMainnet = 8453
    BaseSepolia = 84532

    # Other Chains
    SonicMainnet = 146
    BeraMainnet = 80094


# Mapping of Network enum members to their corresponding NetworkId enum members.
# This dictionary facilitates efficient lookup of network IDs given a network name.
# Note: SolanaMainnet is intentionally excluded as it does not have a numeric chain ID.
#       Always refer to the official documentation for the most up-to-date mappings.
network_to_id: dict[Network, NetworkId] = {
    Network.ArbitrumMainnet: NetworkId.ArbitrumMainnet,
    Network.AvalancheMainnet: NetworkId.AvalancheMainnet,
    Network.BaseMainnet: NetworkId.BaseMainnet,
    Network.BaseSepolia: NetworkId.BaseSepolia,
    Network.BeraMainnet: NetworkId.BeraMainnet,
    Network.BinanceMainnet: NetworkId.BinanceMainnet,
    Network.EthereumMainnet: NetworkId.EthereumMainnet,
    Network.EthereumSepolia: NetworkId.EthereumSepolia,
    Network.GnosisMainnet: NetworkId.GnosisMainnet,
    Network.LineaMainnet: NetworkId.LineaMainnet,
    Network.OptimismMainnet: NetworkId.OptimismMainnet,
    Network.PolygonMainnet: NetworkId.PolygonMainnet,
    Network.SonicMainnet: NetworkId.SonicMainnet,
    Network.ZkSyncMainnet: NetworkId.ZkSyncMainnet,
}

# Mapping of NetworkId enum members (chain IDs) to their corresponding
# Network enum members (network names). This dictionary allows for reverse
# lookup, enabling retrieval of the network name given a chain ID.
# Note:  Solana is not included here as it does not use a standard numeric
#       chain ID.  Always consult official documentation for the most
#       up-to-date mappings.
id_to_network: dict[NetworkId, Network] = {
    NetworkId.ArbitrumMainnet: Network.ArbitrumMainnet,
    NetworkId.AvalancheMainnet: Network.AvalancheMainnet,
    NetworkId.BaseMainnet: Network.BaseMainnet,
    NetworkId.BaseSepolia: Network.BaseSepolia,
    NetworkId.BeraMainnet: Network.BeraMainnet,
    NetworkId.BinanceMainnet: Network.BinanceMainnet,
    NetworkId.EthereumMainnet: Network.EthereumMainnet,
    NetworkId.EthereumSepolia: Network.EthereumSepolia,
    NetworkId.GnosisMainnet: Network.GnosisMainnet,
    NetworkId.LineaMainnet: Network.LineaMainnet,
    NetworkId.OptimismMainnet: Network.OptimismMainnet,
    NetworkId.PolygonMainnet: Network.PolygonMainnet,
    NetworkId.SonicMainnet: Network.SonicMainnet,
    NetworkId.ZkSyncMainnet: Network.ZkSyncMainnet,
}


class ChainConfig:
    """
    Configuration class for a specific blockchain chain.

    This class encapsulates all the necessary information to interact with a
    particular blockchain, including the chain type, network, RPC URLs, and ENS URL.
    """

    def __init__(
        self,
        chain: Chain,
        network: Network,
        rpc_url: str,
        ens_url: str,
        wss_url: str,
    ):
        """
        Initializes a ChainConfig object.

        Args:
            chain: The Chain enum member representing the blockchain type (e.g., Ethereum, Solana).
            network: The Network enum member representing the specific network (e.g., EthereumMainnet).
            rpc_url: The URL for the RPC endpoint of the blockchain.
            ens_url: The URL for the ENS (Ethereum Name Service) endpoint (can be None if not applicable).
            wss_url: The URL for the WebSocket endpoint of the blockchain (can be None if not applicable).
        """

        self._chain = chain
        self._network = network
        self._rpc_url = rpc_url
        self._ens_url = ens_url
        self._wss_url = wss_url

    @property
    def chain(self) -> Chain:
        """
        Returns the Chain enum member.
        """
        return self._chain

    @property
    def network(self) -> Network:
        """
        Returns the Network enum member.
        """
        return self._network

    @property
    def network_id(self) -> int | None:
        """
        Returns the network ID (chain ID) for the configured network, or None if not applicable.
        Uses the global network_to_id mapping to retrieve the ID.
        """
        return network_to_id.get(self._network)

    @property
    def rpc_url(self) -> str:
        """
        Returns the RPC URL.
        """
        return self._rpc_url

    @property
    def ens_url(self) -> str:
        """
        Returns the ENS URL, or None if not applicable.
        """
        return self._ens_url

    @property
    def wss_url(self) -> str:
        """
        Returns the WebSocket URL, or None if not applicable.
        """
        return self._wss_url


class ChainProvider(ABC):
    """
    Abstract base class for providing blockchain chain configurations.

    This class defines the interface for classes responsible for managing and
    providing access to `ChainConfig` objects. Subclasses *must* implement the
    `init_chain_configs` method to populate the available chain configurations.
    """

    def __init__(self):
        """
        Initializes the ChainProvider.

        Sets up an empty dictionary `chain_configs` to store the configurations.
        """
        self.chain_configs: dict[Network, ChainConfig] = {}

    def get_chain_config(self, network: Network) -> ChainConfig:
        """
        Retrieves the chain configuration for a specific network.

        Args:
            network: The `Network` enum member representing the desired network.

        Returns:
            The `ChainConfig` object associated with the given network.

        Raises:
            Exception: If no chain configuration is found for the specified network.
        """
        chain_config = self.chain_configs.get(network)
        if not chain_config:
            raise Exception(f"chain config for network {network} not found")
        return chain_config

    def get_chain_config_by_id(self, network_id: NetworkId) -> ChainConfig:
        """
        Retrieves the chain configuration by network ID.

        This method first looks up the `Network` enum member associated with the
        provided `NetworkId` and then uses `get_chain_config` to retrieve the
        configuration.

        Args:
            network_id: The `NetworkId` enum member representing the desired network ID.

        Returns:
            The `ChainConfig` object associated with the network ID.

        Raises:
            Exception: If no network is found for the given ID or if the
                       chain configuration is not found for the resolved network.
        """
        network = id_to_network.get(network_id)
        if not network:
            raise Exception(f"network with id {network_id} not found")
        return self.get_chain_config(network)

    @abstractmethod
    def init_chain_configs(self, api_key: str) -> dict[Network, ChainConfig]:
        """
        Initializes the chain configurations.

        This *abstract* method *must* be implemented by subclasses.  It is
        responsible for populating the `chain_configs` dictionary with
        `ChainConfig` objects, typically using the provided `api_key` to fetch
        or generate the necessary configuration data.

        Args:
            api_key: The API key used for initializing chain configurations.

        Returns:
            A dictionary mapping `Network` enum members to `ChainConfig` objects.
        """
        raise NotImplementedError


class QuicknodeChainProvider(ChainProvider):
    """
    A concrete implementation of `ChainProvider` for QuickNode.

    This class retrieves chain configuration data from the QuickNode API and
    populates the `chain_configs` dictionary.
    """

    def __init__(self, api_key):
        """
        Initializes the QuicknodeChainProvider.

        Args:
            api_key: Your QuickNode API key.
        """
        super().__init__()
        self.api_key = api_key

    def init_chain_configs(
        self, limit: int = 100, offset: int = 0
    ) -> dict[Network, ChainConfig]:
        """
        Initializes chain configurations by fetching data from the QuickNode API.

        This method retrieves a list of QuickNode endpoints using the provided
        API key and populates the `chain_configs` dictionary with `ChainConfig`
        objects.

        Args:
            limit: The maximum number of endpoints to retrieve (default: 100).
            offset: The number of endpoints to skip (default: 0).

        Returns:
            A dictionary mapping `Network` enum members to `ChainConfig` objects.

        Raises:
            Exception: If an error occurs during the API request or processing
                       the response.  More specific exception types are used
                       for HTTP errors and request errors.
        """
        url = "https://api.quicknode.com/v0/endpoints"
        headers = {
            "Accept": "application/json",
            "x-api-key": self.api_key,
        }
        params = {
            "limit": limit,
            "offset": offset,
        }

        with httpx.Client(timeout=30) as client:  # Set a timeout for the request
            try:
                response = client.get(url, timeout=30, headers=headers, params=params)
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
                json_dict = response.json()

                for item in json_dict["data"]:
                    # Assuming 'item' contains 'chain', 'network', 'http_url', 'wss_url'
                    # and that these values can be used to construct the ChainConfig object
                    chain = Chain(item["chain"])
                    network = Network(item["network"])

                    self.chain_configs[item["network"]] = ChainConfig(
                        chain,
                        network,
                        item["http_url"],
                        item[
                            "http_url"
                        ],  # ens_url is the same as http_url in this case.
                        item["wss_url"],
                    )

            except httpx.HTTPStatusError as http_err:
                raise (f"Quicknode API HTTP Error: {http_err}")
            except httpx.RequestError as req_err:
                raise (f"Quicknode API Request Error: {req_err}")
            except (
                KeyError,
                TypeError,
            ) as e:  # Handle potential data issues in the API response
                raise Exception(
                    f"Error processing QuickNode API response: {e}. Check the API response format."
                )
            except Exception as e:
                raise (f"Quicknode API An unexpected error occurred: {e}")
