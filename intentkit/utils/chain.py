import logging
from abc import ABC, abstractmethod
from enum import IntEnum, StrEnum

import httpx

logger = logging.getLogger(__name__)


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


class QuickNodeNetwork(StrEnum):
    """
    Enum of well-known blockchain network names, based on QuickNode API.

    This list is not exhaustive and might not be completely up-to-date.
    Always consult the official QuickNode documentation for the most accurate
    and current list of supported networks.  Network names can sometimes
    be slightly different from what you might expect.
    """

    # Ethereum Mainnet and Testnets
    EthereumMainnet = "mainnet"
    EthereumGoerli = "goerli"  # Goerli Testnet (deprecated, Sepolia preferred)
    EthereumSepolia = "sepolia"

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


# Mapping of QuickNodeNetwork enum members to their corresponding NetworkId enum members.
# This dictionary facilitates efficient lookup of network IDs given a network name.
# Note: SolanaMainnet is intentionally excluded as it does not have a numeric chain ID.
#       Always refer to the official documentation for the most up-to-date mappings.
network_to_id: dict[QuickNodeNetwork, NetworkId] = {
    QuickNodeNetwork.ArbitrumMainnet: NetworkId.ArbitrumMainnet,
    QuickNodeNetwork.AvalancheMainnet: NetworkId.AvalancheMainnet,
    QuickNodeNetwork.BaseMainnet: NetworkId.BaseMainnet,
    QuickNodeNetwork.BaseSepolia: NetworkId.BaseSepolia,
    QuickNodeNetwork.BeraMainnet: NetworkId.BeraMainnet,
    QuickNodeNetwork.BinanceMainnet: NetworkId.BinanceMainnet,
    QuickNodeNetwork.EthereumMainnet: NetworkId.EthereumMainnet,
    QuickNodeNetwork.EthereumSepolia: NetworkId.EthereumSepolia,
    QuickNodeNetwork.GnosisMainnet: NetworkId.GnosisMainnet,
    QuickNodeNetwork.LineaMainnet: NetworkId.LineaMainnet,
    QuickNodeNetwork.OptimismMainnet: NetworkId.OptimismMainnet,
    QuickNodeNetwork.PolygonMainnet: NetworkId.PolygonMainnet,
    QuickNodeNetwork.SonicMainnet: NetworkId.SonicMainnet,
    QuickNodeNetwork.ZkSyncMainnet: NetworkId.ZkSyncMainnet,
}

# Mapping of NetworkId enum members (chain IDs) to their corresponding
# QuickNodeNetwork enum members (network names). This dictionary allows for reverse
# lookup, enabling retrieval of the network name given a chain ID.
# Note:  Solana is not included here as it does not use a standard numeric
#       chain ID.  Always consult official documentation for the most
#       up-to-date mappings.
id_to_network: dict[NetworkId, QuickNodeNetwork] = {
    NetworkId.ArbitrumMainnet: QuickNodeNetwork.ArbitrumMainnet,
    NetworkId.AvalancheMainnet: QuickNodeNetwork.AvalancheMainnet,
    NetworkId.BaseMainnet: QuickNodeNetwork.BaseMainnet,
    NetworkId.BaseSepolia: QuickNodeNetwork.BaseSepolia,
    NetworkId.BeraMainnet: QuickNodeNetwork.BeraMainnet,
    NetworkId.BinanceMainnet: QuickNodeNetwork.BinanceMainnet,
    NetworkId.EthereumMainnet: QuickNodeNetwork.EthereumMainnet,
    NetworkId.EthereumSepolia: QuickNodeNetwork.EthereumSepolia,
    NetworkId.GnosisMainnet: QuickNodeNetwork.GnosisMainnet,
    NetworkId.LineaMainnet: QuickNodeNetwork.LineaMainnet,
    NetworkId.OptimismMainnet: QuickNodeNetwork.OptimismMainnet,
    NetworkId.PolygonMainnet: QuickNodeNetwork.PolygonMainnet,
    NetworkId.SonicMainnet: QuickNodeNetwork.SonicMainnet,
    NetworkId.ZkSyncMainnet: QuickNodeNetwork.ZkSyncMainnet,
}

# Mapping of agent-level network identifiers to QuickNode network names.
# Agent configuration often uses human-friendly identifiers such as
# "ethereum-mainnet" or "solana" while QuickNode expects the canonical
# network strings defined in `QuickNodeNetwork`.  This mapping bridges the two.
AGENT_NETWORK_TO_QUICKNODE_NETWORK: dict[str, QuickNodeNetwork] = {
    "arbitrum-mainnet": QuickNodeNetwork.ArbitrumMainnet,
    "avalanche-mainnet": QuickNodeNetwork.AvalancheMainnet,
    "aurora-mainnet": QuickNodeNetwork.AuroraMainnet,
    "axelar-mainnet": QuickNodeNetwork.AxelarMainnet,
    "base-mainnet": QuickNodeNetwork.BaseMainnet,
    "base-sepolia": QuickNodeNetwork.BaseSepolia,
    "bera-mainnet": QuickNodeNetwork.BeraMainnet,
    "binance-mainnet": QuickNodeNetwork.BinanceMainnet,
    "bsc-mainnet": QuickNodeNetwork.BinanceMainnet,
    "celo-mainnet": QuickNodeNetwork.CeloMainnet,
    "ethereum": QuickNodeNetwork.EthereumMainnet,
    "ethereum-mainnet": QuickNodeNetwork.EthereumMainnet,
    "ethereum-sepolia": QuickNodeNetwork.EthereumSepolia,
    "evmos-mainnet": QuickNodeNetwork.EvmosMainnet,
    "fantom-mainnet": QuickNodeNetwork.FantomMainnet,
    "frontera-mainnet": QuickNodeNetwork.FronteraMainnet,
    "gnosis": QuickNodeNetwork.GnosisMainnet,
    "gnosis-mainnet": QuickNodeNetwork.GnosisMainnet,
    "goerli": QuickNodeNetwork.EthereumGoerli,
    "kava-mainnet": QuickNodeNetwork.KavaMainnet,
    "linea-mainnet": QuickNodeNetwork.LineaMainnet,
    "matic": QuickNodeNetwork.PolygonMainnet,
    "matic-mainnet": QuickNodeNetwork.PolygonMainnet,
    "moonbeam-mainnet": QuickNodeNetwork.MoonbeamMainnet,
    "near-mainnet": QuickNodeNetwork.NearMainnet,
    "optimism-mainnet": QuickNodeNetwork.OptimismMainnet,
    "persistence-mainnet": QuickNodeNetwork.PersistenceMainnet,
    "polygon": QuickNodeNetwork.PolygonMainnet,
    "polygon-mainnet": QuickNodeNetwork.PolygonMainnet,
    "secret-mainnet": QuickNodeNetwork.SecretMainnet,
    "sepolia": QuickNodeNetwork.EthereumSepolia,
    "solana": QuickNodeNetwork.SolanaMainnet,
    "solana-mainnet": QuickNodeNetwork.SolanaMainnet,
    "sonic-mainnet": QuickNodeNetwork.SonicMainnet,
    "stargaze-mainnet": QuickNodeNetwork.StargazeMainnet,
    "terra-mainnet": QuickNodeNetwork.TerraMainnet,
    "xdai": QuickNodeNetwork.GnosisMainnet,
    "zksync-mainnet": QuickNodeNetwork.ZkSyncMainnet,
}


def resolve_quicknode_network(agent_network_id: str) -> QuickNodeNetwork:
    """Resolve an agent-level network identifier to a QuickNode network.

    Args:
        agent_network_id: Network identifier stored on the agent model.

    Returns:
        The corresponding `QuickNodeNetwork` enum value.

    Raises:
        ValueError: If the agent network identifier is empty or unmapped.
    """

    normalized = (agent_network_id or "").strip().lower()
    if not normalized:
        raise ValueError("agent network_id must be provided")

    mapped_network = AGENT_NETWORK_TO_QUICKNODE_NETWORK.get(normalized)
    if mapped_network:
        return mapped_network

    try:
        return QuickNodeNetwork(normalized)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"unsupported agent network_id: {agent_network_id}") from exc


class ChainConfig:
    """
    Configuration class for a specific blockchain chain.

    This class encapsulates all the necessary information to interact with a
    particular blockchain, including the chain type, network, RPC URLs, and ENS URL.
    """

    def __init__(
        self,
        chain: Chain,
        network: QuickNodeNetwork,
        rpc_url: str,
        ens_url: str,
        wss_url: str,
    ):
        """
        Initializes a ChainConfig object.

        Args:
            chain: The Chain enum member representing the blockchain type (e.g., Ethereum, Solana).
            network: The QuickNodeNetwork enum member representing the specific network (e.g., EthereumMainnet).
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
    def network(self) -> QuickNodeNetwork:
        """
        Returns the QuickNodeNetwork enum member.
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
        self.chain_configs: dict[QuickNodeNetwork, ChainConfig] = {}

    def get_chain_config(self, network_id: str) -> ChainConfig:
        """
        Retrieves the chain configuration for a specific agent network identifier.

        Args:
            network_id: The agent-level network identifier (e.g., "base-mainnet").

        Returns:
            The `ChainConfig` object associated with the given network.

        Raises:
            Exception: If no chain configuration is found for the specified network.
        """
        try:
            quicknode_network = resolve_quicknode_network(network_id)
        except ValueError as exc:
            raise Exception(f"unsupported network_id: {network_id}") from exc

        return self._get_chain_config_by_quicknode_network(quicknode_network)

    def _get_chain_config_by_quicknode_network(
        self, quicknode_network: QuickNodeNetwork
    ) -> ChainConfig:
        chain_config = self.chain_configs.get(quicknode_network)
        if not chain_config:
            raise Exception(f"chain config for network {quicknode_network} not found")
        return chain_config

    def get_chain_config_by_id(self, network_id: NetworkId) -> ChainConfig:
        """
        Retrieves the chain configuration by network ID.

        This method first looks up the `QuickNodeNetwork` enum member associated
        with the provided `NetworkId` and then retrieves the corresponding
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
        return self._get_chain_config_by_quicknode_network(network)

    @abstractmethod
    def init_chain_configs(self, *_, **__) -> None:
        """
        Initializes the chain configurations.

        This *abstract* method *must* be implemented by subclasses.  It is
        responsible for populating the `chain_configs` dictionary with
        `ChainConfig` objects, typically using the provided `api_key` to fetch
        or generate the necessary configuration data.

        The method must mutate `self.chain_configs` in-place and does not need
        to return anything.
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

    def init_chain_configs(self, limit: int = 100, offset: int = 0) -> None:
        """
        Initializes chain configurations by fetching data from the QuickNode API.

        This method retrieves a list of QuickNode endpoints using the provided
        API key and populates the `chain_configs` dictionary with `ChainConfig`
        objects.  Errors are logged and do not raise exceptions so that any
        successful configurations remain available.

        Args:
            limit: The maximum number of endpoints to retrieve (default: 100).
            offset: The number of endpoints to skip (default: 0).
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

        with httpx.Client(timeout=30) as client:
            try:
                response = client.get(url, timeout=30, headers=headers, params=params)
                response.raise_for_status()
                json_dict = response.json()
            except httpx.HTTPStatusError as http_err:
                logger.error(
                    "QuickNode API HTTP error while initializing chain configs: %s",
                    http_err,
                )
                return
            except httpx.RequestError as req_err:
                logger.error(
                    "QuickNode API request error while initializing chain configs: %s",
                    req_err,
                )
                return
            except Exception as exc:
                logger.exception(
                    "Unexpected error while fetching QuickNode chain configs: %s", exc
                )
                return

        data = json_dict.get("data", [])
        if not isinstance(data, list):
            logger.error(
                "QuickNode chain configs response 'data' is not a list: %s", data
            )
            return

        for item in data:
            if not isinstance(item, dict):
                logger.error("Skipping malformed QuickNode chain entry: %s", item)
                continue

            try:
                chain_value = item["chain"]
                network_value = item["network"]
                rpc_url = item["http_url"]
                chain = Chain(chain_value)
                network = QuickNodeNetwork(network_value)
                ens_url = item.get("ens_url", rpc_url)
                wss_url = item.get("wss_url")
            except ValueError as exc:
                logger.debug("Skipping unsupported QuickNode entry %s: %s", item, exc)
                continue
            except KeyError as exc:
                logger.error(
                    "Missing field %s in QuickNode chain config item %s", exc, item
                )
                continue
            except Exception as exc:
                logger.error(
                    "Failed processing QuickNode chain config item %s: %s", item, exc
                )
                continue

            self.chain_configs[network] = ChainConfig(
                chain,
                network,
                rpc_url,
                ens_url,
                wss_url,
            )
