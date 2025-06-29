from typing import Type

from pydantic import BaseModel, Field

from intentkit.abstracts.agent import AgentStoreABC
from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill
from intentkit.utils.chain import ChainConfig, ChainProvider, Network


class CrossmintChainConfig:
    """
    Configuration class for a blockchain chain specific to Crossmint.

    This class combines a generic `ChainConfig` with a Crossmint-specific
    `network_alias`, allowing Crossmint to identify and manage different
    configurations for the same underlying blockchain network.  This is useful
    because Crossmint might use different names or configurations for the same
    blockchain depending on the context (e.g., different environments or
    integrations).
    """

    def __init__(self, chain_config: ChainConfig, network_alias: str):
        """
        Initializes a CrossmintChainConfig object.

        Args:
            chain_config: The underlying `ChainConfig` object for the blockchain.
            network_alias: A Crossmint-specific alias or identifier for this
                           configuration.  This can be used to distinguish
                           between different configurations for the same
                           blockchain.
        """
        self._chain_config = chain_config
        self._network_alias = network_alias

    @property
    def chain_config(self) -> ChainConfig:
        """
        Returns the underlying `ChainConfig` object.
        """
        return self._chain_config

    @property
    def network_alias(self) -> str:
        """
        Returns the Crossmint-specific network alias.
        """
        return self._network_alias


class CrossmintChainProviderAdapter:
    """
    Adapter class to provide Crossmint-specific chain configurations.

    This class adapts a generic `ChainProvider` to provide `CrossmintChainConfig`
    objects.  It filters the available chain configurations from the underlying
    `ChainProvider` based on a list of supported networks and assigns
    Crossmint-specific aliases.
    """

    def __init__(self, chain_provider: ChainProvider, networks: list[Network]):
        """
        Initializes the CrossmintChainProviderAdapter.

        Args:
            chain_provider: The underlying `ChainProvider` instance.
            networks: A list of `Network` enum members representing the networks
                      supported by Crossmint.  Only configurations for these
                      networks will be included.

        Raises:
            Exception: If no supported chain configuration is found in the provided chain_provider.
        """
        self.chain_provider = chain_provider
        self.chain_configs: list[CrossmintChainConfig] = []

        for network, chain_config in self.chain_provider.chain_configs.items():
            if network not in networks:
                continue  # Skip networks not supported by Crossmint

            network_alias = network  # Default alias is the network name

            if network == Network.BaseMainnet:
                network_alias = "base"  # Example: Crossmint alias for Base Mainnet

            self.chain_configs.append(CrossmintChainConfig(chain_config, network_alias))

        if len(self.chain_configs) == 0:
            raise ("Failed to init crossmint chain provider, no supported chain found")


class GoatBaseTool(IntentKitSkill):
    """Base class for Goat tools."""

    private_key: str = Field(description="Wallet Private Key")
    rpc_node: str | None = Field(None, description="RPC nodes for different networks")
    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    agent_id: str = Field(description="The ID of the agent")
    agent_store: AgentStoreABC = Field(
        description="The agent store for persisting data"
    )
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )
