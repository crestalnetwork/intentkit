from langchain_core.skills import IntentKitSkill
import ccxt
import pandas as pd

class CEXBaseSkill(IntentKitSkill):
    """
    Base class for all CEX (Centralized Exchange) skills. Provides shared infrastructure like the ccxt client.
    """
    def __init__(self, api_key: str, secret: str, password: str, exchange: str = "okx"):
        self.exchange = ccxt.__dict__[exchange]({
            'apiKey': api_key,
            'secret': secret,
            'password': password,
            'enableRateLimit': True,
        })

    def fetch_historical_data(self, symbol, timeframe, limit=200):
        """Fetch historical OHLCV data."""
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df