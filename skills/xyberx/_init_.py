from langchain_core.tools import BaseTool
from skills.crestal.search_web3_services import search_web3_services
from skills.crestal.trade_on_okx import TradeOnOkx  # Import the new skill

def get_common_skill(name: str) -> BaseTool:
    if name == "search_web3_services":
        return search_web3_services
    elif name == "trade_on_okx":  # Add the condition for the new tool
        # Replace with actual OKX API credentials
        api_key = "your_okx_api_key"
        secret = "your_okx_secret"
        password = "your_okx_password"
        return TradeOnOkx(api_key, secret, password)
