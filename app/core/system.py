from typing import Optional

from models.w3 import W3Token
from utils.chain import Network


class SystemStore:
    def __init__(self) -> None:
        pass

    async def get_token(self, symbol: str, network: Network) -> Optional[W3Token]:
        return await W3Token.get(symbol, network)

    async def get_all_wellknown_tokens(self) -> list[W3Token]:
        return await W3Token.get_well_known()
