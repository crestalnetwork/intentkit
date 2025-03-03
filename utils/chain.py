from abc import ABC, abstractmethod
from enum import Enum, StrEnum

import httpx
from pydantic import BaseModel, Field


class EventSignature(StrEnum):
    Transfer = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


class ChainType(Enum):
    """
    ChainType is an enumeration that represents different types of blockchain networks.
    """

    EVM = 1
    Solana = 2
    Cosmos = 3
    Other = 4


class ChainData(BaseModel):
    title: str = Field(description="The name of the blockchain.")
    chain_type: ChainType = Field(description="The type of the blockchain.")


class Chain(Enum):
    """
    Enum of supported blockchain chains, using QuickNode's naming conventions.

    This list is based on common chain names used by QuickNode, but it's essential
    to consult the official QuickNode documentation for the most accurate and
    up-to-date list of supported chains and their exact names.  Chain names can
    sometimes be slightly different from what you might expect.
    """

    # EVM Chains
    Ethereum = ChainData(title="eth", chain_type=ChainType.EVM)  # Or "ethereum"
    Avalanche = ChainData(title="avax", chain_type=ChainType.EVM)  # Or "avalanche"
    Binance = ChainData(title="bsc", chain_type=ChainType.EVM)  # BNB Smart Chain
    Polygon = ChainData(title="matic", chain_type=ChainType.EVM)  # Or "polygon"
    Gnosis = ChainData(title="gnosis", chain_type=ChainType.EVM)  # Or "xdai"
    Celo = ChainData(title="celo", chain_type=ChainType.EVM)
    Fantom = ChainData(title="fantom", chain_type=ChainType.EVM)
    Moonbeam = ChainData(title="moonbeam", chain_type=ChainType.EVM)
    Aurora = ChainData(title="aurora", chain_type=ChainType.EVM)
    Arbitrum = ChainData(title="arbitrum", chain_type=ChainType.EVM)
    Optimism = ChainData(title="optimism", chain_type=ChainType.EVM)
    Linea = ChainData(title="linea", chain_type=ChainType.EVM)
    ZkSync = ChainData(title="zksync", chain_type=ChainType.EVM)

    # Base
    Base = ChainData(title="base", chain_type=ChainType.EVM)

    # Cosmos Ecosystem
    CosmosHub = ChainData(
        title="cosmos", chain_type=ChainType.Cosmos
    )  # Or "cosmos-hub"
    Osmosis = ChainData(title="osmosis", chain_type=ChainType.Cosmos)
    Juno = ChainData(title="juno", chain_type=ChainType.Cosmos)
    Evmos = ChainData(title="evmos", chain_type=ChainType.Cosmos)
    Kava = ChainData(title="kava", chain_type=ChainType.Cosmos)
    Persistence = ChainData(title="persistence", chain_type=ChainType.Cosmos)
    Secret = ChainData(title="secret", chain_type=ChainType.Cosmos)
    Stargaze = ChainData(title="stargaze", chain_type=ChainType.Cosmos)
    Terra = ChainData(title="terra", chain_type=ChainType.Cosmos)  # Or "terra-classic"
    Axelar = ChainData(title="axelar", chain_type=ChainType.Cosmos)

    # Solana
    Solana = ChainData(title="sol", chain_type=ChainType.Solana)  # Or "solana"

    # Other Chains
    Sonic = ChainData(title="sonic", chain_type=ChainType.Other)
    Bera = ChainData(title="bera", chain_type=ChainType.Other)
    Near = ChainData(title="near", chain_type=ChainType.Other)
    Frontera = ChainData(title="frontera", chain_type=ChainType.Other)

    # def __str__(self):
    #     return self.value.title


def get_chain_by_title(title: str) -> Chain:
    for chain in Chain:
        if chain.value.title == title:
            return chain
    return None


class NetworkTitle(StrEnum):
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
    CosmosHubMainnet = "cosmos-hub-mainnet"  # Or just "cosmos", Cosmos doesn't have a consistent chain ID
    OsmosisMainnet = "osmosis-mainnet"  # Or just "osmosis", Cosmos doesn't have a consistent chain ID
    JunoMainnet = (
        "juno-mainnet"  # Or just "juno", Cosmos doesn't have a consistent chain ID
    )

    # Solana (Note: Solana uses cluster names, not typical network names)
    SolanaMainnet = "solana-mainnet"  # Or "solana", Solana doesn't have a chain ID

    # Other Chains
    SonicMainnet = "sonic-mainnet"
    BeraMainnet = "bera-mainnet"
    NearMainnet = "near-mainnet"  # Or just "near", Near doesn't have a chain ID
    KavaMainnet = (
        "kava-mainnet"  # Or just "kava", Kava chain ID can vary depending on zone
    )
    EvmosMainnet = (
        "evmos-mainnet"  # Or just "evmos", Evmos chain ID can vary depending on zone
    )
    PersistenceMainnet = "persistence-mainnet"  # Or just "persistence", Persistence chain ID can vary depending on zone
    SecretMainnet = (
        "secret-mainnet"  # Or just "secret", Secret chain ID can vary depending on zone
    )
    StargazeMainnet = "stargaze-mainnet"  # Or just "stargaze", Stargaze chain ID can vary depending on zone
    TerraMainnet = (
        "terra-mainnet"  # Or "terra-classic", Terra chain ID can vary depending on zone
    )
    AxelarMainnet = (
        "axelar-mainnet"  # Or just "axelar", Axelar chain ID can vary depending on zone
    )
    FronteraMainnet = "frontera-mainnet"


class NetworkData(BaseModel):
    id: str = Field(description="The id of the network (chain id).")
    title: NetworkTitle = Field(description="The name of the blockchain.")
    chain: Chain = Field(description="The Chain technology of the network")
    block_time: float = Field(description="Average block time in seconds.")


class Network(Enum):
    """
    Enum of well-known blockchain network names, based on QuickNode API.

    This list is not exhaustive and might not be completely up-to-date.
    Always consult the official QuickNode documentation for the most accurate
    and current list of supported networks.  Network names can sometimes
    be slightly different from what you might expect.
    """

    # Ethereum Mainnet and Testnets
    EthereumMainnet = NetworkData(
        title=NetworkTitle.EthereumMainnet,
        id="1",
        chain=Chain.Ethereum,
        block_time=13.5,  # Approximate block time in seconds
    )
    EthereumGoerli = NetworkData(
        title=NetworkTitle.EthereumGoerli,
        id="5",
        chain=Chain.Ethereum,
        block_time=15,  # Approximate block time in seconds
    )
    EthereumSepolia = NetworkData(
        title=NetworkTitle.EthereumSepolia,
        id="11155111",
        chain=Chain.Ethereum,
        block_time=12,  # Approximate block time in seconds
    )

    # Layer 2s on Ethereum
    ArbitrumMainnet = NetworkData(
        title=NetworkTitle.ArbitrumMainnet,
        id="42161",
        chain=Chain.Arbitrum,
        block_time=0.25,  # Approximate block time in seconds
    )
    OptimismMainnet = NetworkData(
        title=NetworkTitle.OptimismMainnet,
        id="10",
        chain=Chain.Optimism,
        block_time=2,  # Approximate block time in seconds
    )
    LineaMainnet = NetworkData(
        title=NetworkTitle.LineaMainnet,
        id="59144",
        chain=Chain.Linea,
        block_time=1,  # Approximate block time in seconds
    )
    ZkSyncMainnet = NetworkData(
        title=NetworkTitle.ZkSyncMainnet,
        id="324",
        chain=Chain.ZkSync,
        block_time=3,  # Approximate block time in seconds
    )

    # Other EVM Chains
    AvalancheMainnet = NetworkData(
        title=NetworkTitle.AvalancheMainnet,
        id="43114",
        chain=Chain.Avalanche,
        block_time=2,  # Approximate block time in seconds
    )
    BinanceMainnet = NetworkData(
        title=NetworkTitle.BinanceMainnet,
        id="56",
        chain=Chain.Binance,
        block_time=3,  # Approximate block time in seconds
    )
    PolygonMainnet = NetworkData(
        title=NetworkTitle.PolygonMainnet,
        id="137",
        chain=Chain.Polygon,
        block_time=2.5,  # Approximate block time in seconds
    )
    GnosisMainnet = NetworkData(
        title=NetworkTitle.GnosisMainnet,
        id="100",
        chain=Chain.Gnosis,
        block_time=5,  # Approximate block time in seconds
    )
    CeloMainnet = NetworkData(
        title=NetworkTitle.CeloMainnet,
        id="42220",
        chain=Chain.Celo,
        block_time=5,  # Approximate block time in seconds
    )
    FantomMainnet = NetworkData(
        title=NetworkTitle.FantomMainnet,
        id="250",
        chain=Chain.Fantom,
        block_time=1,  # Approximate block time in seconds
    )
    MoonbeamMainnet = NetworkData(
        title=NetworkTitle.MoonbeamMainnet,
        id="1284",
        chain=Chain.Moonbeam,
        block_time=12,  # Approximate block time in seconds
    )
    AuroraMainnet = NetworkData(
        title=NetworkTitle.AuroraMainnet,
        id="1313161554",
        chain=Chain.Aurora,
        block_time=1,  # Approximate block time in seconds
    )

    # Base
    BaseMainnet = NetworkData(
        title=NetworkTitle.BaseMainnet,
        id="8453",
        chain=Chain.Base,
        block_time=2,  # Approximate block time in seconds
    )
    BaseSepolia = NetworkData(
        title=NetworkTitle.BaseSepolia,
        id="84532",
        chain=Chain.Base,
        block_time=2,  # Approximate block time in seconds
    )

    # Cosmos Ecosystem
    CosmosHubMainnet = NetworkData(
        title=NetworkTitle.CosmosHubMainnet,
        id="cosmoshub-4",
        chain=Chain.CosmosHub,
        block_time=6,  # Approximate block time in seconds
    )
    OsmosisMainnet = NetworkData(
        title=NetworkTitle.OsmosisMainnet,
        id="osmosis-1",
        chain=Chain.Osmosis,
        block_time=6,  # Approximate block time in seconds
    )
    JunoMainnet = NetworkData(
        title=NetworkTitle.JunoMainnet,
        id="juno-1",
        chain=Chain.Juno,
        block_time=6,  # Approximate block time in seconds
    )

    # Solana
    SolanaMainnet = NetworkData(
        title=NetworkTitle.SolanaMainnet,
        id="-1",
        chain=Chain.Solana,
        block_time=0.4,  # Approximate block time in seconds
    )

    # Other Chains
    SonicMainnet = NetworkData(
        title=NetworkTitle.SonicMainnet, id="146", chain=Chain.Sonic, block_time=2
    )
    BeraMainnet = NetworkData(
        title=NetworkTitle.BeraMainnet, id="80094", chain=Chain.Bera, block_time=6
    )
    NearMainnet = NetworkData(
        title=NetworkTitle.NearMainnet,
        id="near",
        chain=Chain.Near,
        block_time=1,  # Near ID is not a number, but a string.
    )
    KavaMainnet = NetworkData(
        title=NetworkTitle.KavaMainnet,
        id="kava_2222-10",
        chain=Chain.Kava,
        block_time=6,  # current kava mainnet chain ID.
    )
    EvmosMainnet = NetworkData(
        title=NetworkTitle.EvmosMainnet,
        id="evmos_9001-2",
        chain=Chain.Evmos,
        block_time=6,  # example of evmos ID. Version will change.
    )
    PersistenceMainnet = NetworkData(
        title=NetworkTitle.PersistenceMainnet,
        id="core-1",
        chain=Chain.Persistence,
        block_time=6,
    )
    SecretMainnet = NetworkData(
        title=NetworkTitle.SecretMainnet,
        id="secret-4",
        chain=Chain.Secret,
        block_time=6,
    )
    StargazeMainnet = NetworkData(
        title=NetworkTitle.StargazeMainnet,
        id="stargaze-1",
        chain=Chain.Stargaze,
        block_time=6,
    )
    TerraMainnet = NetworkData(
        title=NetworkTitle.TerraMainnet, id="phoenix-1", chain=Chain.Terra, block_time=6
    )
    AxelarMainnet = NetworkData(
        title=NetworkTitle.AxelarMainnet,
        id="axelar-dojo-1",
        chain=Chain.Axelar,
        block_time=6,
    )
    FronteraMainnet = NetworkData(
        title=NetworkTitle.FronteraMainnet,
        id="frontera-1",
        chain=Chain.Frontera,
        block_time=6,
    )


def get_network_by_title(title: NetworkTitle) -> Network:
    for network in Network:
        if network.value.title == title:
            return network
    return None


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
        self.chain_configs: dict[NetworkTitle, ChainConfig] = {}

    def get_chain_config(self, network_title: NetworkTitle) -> ChainConfig:
        """
        Retrieves the chain configuration for a specific network.

        Args:
            network: The `Network` enum member representing the desired network.

        Returns:
            The `ChainConfig` object associated with the given network.

        Raises:
            Exception: If no chain configuration is found for the specified network.
        """
        chain_config = self.chain_configs.get(network_title)
        if not chain_config:
            raise Exception(f"chain config for network {network_title} not found")
        return chain_config

    @abstractmethod
    def init_chain_configs(self, api_key: str) -> dict[NetworkTitle, ChainConfig]:
        """
        Initializes the chain configurations.

        This *abstract* method *must* be implemented by subclasses.  It is
        responsible for populating the `chain_configs` dictionary with
        `ChainConfig` objects, typically using the provided `api_key` to fetch
        or generate the necessary configuration data.

        Args:
            api_key: The API key used for initializing chain configurations.

        Returns:
            A dictionary mapping `NetworkTitle` enum members to `ChainConfig` objects.
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
                    chain = get_chain_by_title(item["chain"])
                    network = get_network_by_title(item["network"])

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


def get_padded_address(address):
    """Pads an Ethereum address with leading zeros to 64 hex characters."""
    if not address.startswith("0x"):
        raise ValueError("Address must start with '0x'")

    return "0x" + address[2:].lower().zfill(64)
