import logging
from abc import ABC, abstractmethod
from enum import IntEnum, StrEnum
from typing import final, override

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


class SupportedNetwork(StrEnum):
    """
    Enum of supported blockchain networks for IntentKit.
    """

    BaseMainnet = "base-mainnet"
    EthereumMainnet = "ethereum-mainnet"
    PolygonMainnet = "polygon-mainnet"
    ArbitrumMainnet = "arbitrum-mainnet"
    OptimismMainnet = "optimism-mainnet"
    BnbMainnet = "bnb-mainnet"
    BaseSepolia = "base-sepolia"


class QuickNodeSlug(StrEnum):
    """
    Enum of well-known blockchain network names, based on QuickNode API.
    Used internally for mapping.
    """

    # Ethereum Mainnet and Testnets
    EthereumMainnet = "mainnet"
    EthereumSepolia = "sepolia"

    # Layer 2s on Ethereum
    ArbitrumMainnet = "arbitrum-mainnet"
    OptimismMainnet = "optimism-mainnet"  # Or just "optimism"

    # Other EVM Chains
    BinanceMainnet = "bsc"  # BNB Smart Chain (BSC)
    PolygonMainnet = "matic"  # Or "polygon-mainnet"

    # Base
    BaseMainnet = "base-mainnet"
    BaseSepolia = "base-sepolia"

    # BNB
    BnbMainnet = "bnb-mainnet"


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

    # BNB
    BnbMainnet = 56

    # Other Chains
    SonicMainnet = 146
    BeraMainnet = 80094


# QuickNode may return short chain/network identifiers that map to existing enums.
QUICKNODE_CHAIN_ALIASES: dict[str, str] = {
    "arb": Chain.Arbitrum.value,
}
QUICKNODE_NETWORK_ALIASES: dict[str, str] = {
    "optimism": QuickNodeSlug.OptimismMainnet.value,
}

# Mapping of SupportedNetwork enum members to their corresponding NetworkId enum members.
network_to_id: dict[SupportedNetwork, NetworkId] = {
    SupportedNetwork.ArbitrumMainnet: NetworkId.ArbitrumMainnet,
    SupportedNetwork.BaseMainnet: NetworkId.BaseMainnet,
    SupportedNetwork.BaseSepolia: NetworkId.BaseSepolia,
    SupportedNetwork.BnbMainnet: NetworkId.BnbMainnet,
    SupportedNetwork.EthereumMainnet: NetworkId.EthereumMainnet,
    SupportedNetwork.OptimismMainnet: NetworkId.OptimismMainnet,
    SupportedNetwork.PolygonMainnet: NetworkId.PolygonMainnet,
}

# Mapping of NetworkId enum members (chain IDs) to their corresponding
# SupportedNetwork enum members.
id_to_network: dict[NetworkId, SupportedNetwork] = {
    NetworkId.ArbitrumMainnet: SupportedNetwork.ArbitrumMainnet,
    NetworkId.BaseMainnet: SupportedNetwork.BaseMainnet,
    NetworkId.BaseSepolia: SupportedNetwork.BaseSepolia,
    NetworkId.BinanceMainnet: SupportedNetwork.BnbMainnet,
    NetworkId.BnbMainnet: SupportedNetwork.BnbMainnet,
    NetworkId.EthereumMainnet: SupportedNetwork.EthereumMainnet,
    # NetworkId.EthereumSepolia: SupportedNetwork.EthereumSepolia, # Sepolia is not explicitly in SupportedNetwork but BaseSepolia is? Wait, BaseSepolia is separate.
    # Ah, SupportedNetwork has BaseSepolia but not EthereumSepolia?
    # User list: base-mainnet, ethereum-mainnet, polygon-mainnet, arbitrum-mainnet, optimism-mainnet, bnb-mainnet, base-sepolia
    # So Ethereum Sepolia is NOT supported as a primary network anymore according to strict user request.
    NetworkId.OptimismMainnet: SupportedNetwork.OptimismMainnet,
    NetworkId.PolygonMainnet: SupportedNetwork.PolygonMainnet,
}

# Mapping of agent-level network identifiers to QuickNode network names.
# Agent configuration often uses human-friendly identifiers such as
# "ethereum-mainnet" or "solana" while QuickNode expects the canonical
# network strings defined in `QuickNodeNetwork`.  This mapping bridges the two.
# Mapping of agent-level network identifiers to SupportedNetwork.
# The user's requested list includes:
# "base-mainnet", "ethereum-mainnet", "polygon-mainnet",
# "arbitrum-mainnet", "optimism-mainnet", "bnb-mainnet", "base-sepolia"
AGENT_NETWORK_TO_SUPPORTED_NETWORK: dict[str, SupportedNetwork] = {
    "arbitrum-mainnet": SupportedNetwork.ArbitrumMainnet,
    "base-mainnet": SupportedNetwork.BaseMainnet,
    "base-sepolia": SupportedNetwork.BaseSepolia,
    "binance-mainnet": SupportedNetwork.BnbMainnet,
    "bnb-mainnet": SupportedNetwork.BnbMainnet,
    "bsc-mainnet": SupportedNetwork.BnbMainnet,  # alias
    "ethereum": SupportedNetwork.EthereumMainnet,
    "ethereum-mainnet": SupportedNetwork.EthereumMainnet,
    "matic": SupportedNetwork.PolygonMainnet,
    "matic-mainnet": SupportedNetwork.PolygonMainnet,
    "optimism-mainnet": SupportedNetwork.OptimismMainnet,
    "polygon": SupportedNetwork.PolygonMainnet,
    "polygon-mainnet": SupportedNetwork.PolygonMainnet,
}


def resolve_supported_network(agent_network_id: str) -> SupportedNetwork:
    """Resolve an agent-level network identifier to a SupportedNetwork.

    Args:
        agent_network_id: Network identifier stored on the agent model.

    Returns:
        The corresponding `SupportedNetwork` enum value.

    Raises:
        ValueError: If the agent network identifier is empty or unmapped.
    """

    normalized = (agent_network_id or "").strip().lower()
    if not normalized:
        raise ValueError("agent network_id must be provided")

    mapped_network = AGENT_NETWORK_TO_SUPPORTED_NETWORK.get(normalized)
    if mapped_network:
        return mapped_network

    try:
        return SupportedNetwork(normalized)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"unsupported agent network_id: {agent_network_id}") from exc


@final
class ChainConfig:
    """
    Configuration class for a specific blockchain chain.

    This class encapsulates all the necessary information to interact with a
    particular blockchain, including the chain type, network, RPC URLs, and ENS URL.
    """

    def __init__(
        self,
        chain: Chain,
        network: SupportedNetwork,
        rpc_url: str,
        ens_url: str,
        wss_url: str,
    ):
        """
        Initializes a ChainConfig object.

        Args:
            chain: The Chain enum member representing the blockchain type (e.g., Ethereum, Solana).
            network: The SupportedNetwork enum member representing the specific network (e.g., EthereumMainnet).
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
    def network(self) -> SupportedNetwork:
        """
        Returns the SupportedNetwork enum member.
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
        self.chain_configs: dict[SupportedNetwork, ChainConfig] = {}

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
            supported_network = resolve_supported_network(network_id)
        except ValueError as exc:
            raise Exception(f"unsupported network_id: {network_id}") from exc

        return self._get_chain_config_by_supported_network(supported_network)

    def _get_chain_config_by_supported_network(
        self, supported_network: SupportedNetwork
    ) -> ChainConfig:
        chain_config = self.chain_configs.get(supported_network)
        if not chain_config:
            raise Exception(f"chain config for network {supported_network} not found")
        return chain_config

    def get_chain_config_by_id(self, network_id: NetworkId) -> ChainConfig:
        """
        Retrieves the chain configuration by network ID.

        This method first looks up the `SupportedNetwork` enum member associated
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
        return self._get_chain_config_by_supported_network(network)

    @abstractmethod
    def init_chain_configs(self, *_: object, **__: object) -> None:
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


@final
class QuicknodeChainProvider(ChainProvider):
    """
    A concrete implementation of `ChainProvider` for QuickNode.

    This class retrieves chain configuration data from the QuickNode API and
    populates the `chain_configs` dictionary.
    """

    def __init__(self, api_key: str):
        """
        Initializes the QuicknodeChainProvider.

        Args:
            api_key: Your QuickNode API key.
        """
        super().__init__()
        self.api_key: str = api_key

    @override
    def init_chain_configs(
        self, limit: int = 100, offset: int = 0, *args: object, **kwargs: object
    ) -> None:
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
                chain_value = str(item["chain"]).lower()
                network_value = str(item["network"]).lower()
                rpc_url = item["http_url"]
                chain_value = QUICKNODE_CHAIN_ALIASES.get(chain_value, chain_value)
                network_value = QUICKNODE_NETWORK_ALIASES.get(
                    network_value, network_value
                )
                chain = Chain(chain_value)
                # Ensure we have a valid QuickNodeSlug first
                try:
                    qn_slug = QuickNodeSlug(network_value)
                except ValueError:
                    logger.debug("Skipping unknown QuickNode slug: %s", network_value)
                    continue

                # Now map QuickNodeSlug to SupportedNetwork
                # We need a mapping from QuickNodeSlug to SupportedNetwork
                # Since the values might not match exactly or we only support a subset
                supported_network = self._map_slug_to_supported_network(qn_slug)
                if not supported_network:
                    logger.debug(
                        "QuickNode slug %s not in SupportedNetwork list", qn_slug
                    )
                    continue

                ens_url = item.get("ens_url", rpc_url)
                wss_url = item.get("wss_url") or ""
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

            self.chain_configs[supported_network] = ChainConfig(
                chain,
                supported_network,
                rpc_url,
                ens_url,
                wss_url,
            )

    def _map_slug_to_supported_network(
        self, slug: QuickNodeSlug
    ) -> SupportedNetwork | None:
        # Simple mapping based on values or explicit map
        # Since we aligned SupportedNetwork values with expected user inputs,
        # we can map carefully.
        slug_map: dict[QuickNodeSlug, SupportedNetwork] = {
            QuickNodeSlug.EthereumMainnet: SupportedNetwork.EthereumMainnet,
            # QuickNodeSlug.EthereumSepolia: None,  # Not supported by user request
            QuickNodeSlug.ArbitrumMainnet: SupportedNetwork.ArbitrumMainnet,
            QuickNodeSlug.OptimismMainnet: SupportedNetwork.OptimismMainnet,
            QuickNodeSlug.BinanceMainnet: SupportedNetwork.BnbMainnet,
            QuickNodeSlug.PolygonMainnet: SupportedNetwork.PolygonMainnet,
            QuickNodeSlug.BaseMainnet: SupportedNetwork.BaseMainnet,
            QuickNodeSlug.BaseSepolia: SupportedNetwork.BaseSepolia,
            # QuickNodeSlug.BnbMainnet: SupportedNetwork.BnbMainnet, # Duplicate? check definition
        }
        # Handle BnbMainnet separate if it exists in QuickNodeSlug
        if slug == QuickNodeSlug.BnbMainnet:
            return SupportedNetwork.BnbMainnet

        return slug_map.get(slug)


@final
class InfuraChainProvider(ChainProvider):
    """
    A concrete implementation of `ChainProvider` for Infura.

    This class provides chain configuration data using hardcoded mappings
    and Infura V3 URLs.
    """

    INFURA_NETWORKS: dict[SupportedNetwork, tuple[Chain, str]] = {
        SupportedNetwork.EthereumMainnet: (Chain.Ethereum, "mainnet"),
        # SupportedNetwork.EthereumSepolia: (Chain.Ethereum, "sepolia"), # Not supported
        SupportedNetwork.ArbitrumMainnet: (Chain.Arbitrum, "arbitrum-mainnet"),
        SupportedNetwork.OptimismMainnet: (Chain.Optimism, "optimism-mainnet"),
        SupportedNetwork.PolygonMainnet: (Chain.Polygon, "polygon-mainnet"),
        SupportedNetwork.BaseMainnet: (Chain.Base, "base-mainnet"),
        SupportedNetwork.BaseSepolia: (Chain.Base, "base-sepolia"),
        SupportedNetwork.BnbMainnet: (Chain.Binance, "bsc-mainnet"),
    }

    def __init__(self, api_key: str) -> None:
        """
        Initializes the InfuraChainProvider.

        Args:
            api_key: Your Infura API key.
        """
        super().__init__()
        self.api_key: str = api_key

    @override
    def init_chain_configs(self, *_: object, **__: object) -> None:
        """
        Initializes chain configurations using hardcoded Infura mappings.
        """
        for network, (chain, infura_name) in self.INFURA_NETWORKS.items():
            rpc_url = f"https://{infura_name}.infura.io/v3/{self.api_key}"
            wss_url = f"wss://{infura_name}.infura.io/ws/v3/{self.api_key}"

            # Ensure we default ens_url
            ens_url = rpc_url

            self.chain_configs[network] = ChainConfig(
                chain,
                network,
                rpc_url,
                ens_url,
                wss_url,
            )
