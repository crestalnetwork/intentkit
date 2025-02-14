from enum import Enum
from typing import Literal


class NetworkType(Enum):
    Mainnet = 1
    Testnet = 2


class ChainConfig:
    def __init__(
        self,
        name: Literal["base"],
        network_type: NetworkType,
        rpc_url: str,
        ens_url: str,
    ):
        self._name = name
        self._rpc_url = rpc_url
        self._ens_url = ens_url
        self._network_type = network_type

    @property
    def name(self) -> str:
        return self._name

    @property
    def network_type(self) -> NetworkType:
        return self._network_type

    @property
    def rpc_url(self) -> str:
        return self._rpc_url

    @property
    def ens_url(self) -> str:
        return self._ens_url
