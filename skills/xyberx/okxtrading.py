from langchain_core.tools import BaseTool
import ccxt
import pandas as pd
import numpy as np

class TradeOnOkx(BaseTool):
    """
    A skill to trade cryptocurrencies on OKX using RSI, CCI, Bollinger Bands, and EMA 200 indicators.
    """
    name = "trade_on_okx"
    description = "Automatically trade crypto on OKX using technical indicators for decision-making."

    def __init__(self, api_key, secret, password):
        self.okx = ccxt.okx({
            'apiKey': api_key,
            'secret': secret,
            'password': password,
            'enableRateLimit': True,
        })

    def fetch_historical_data(self, symbol, timeframe, limit=200):
        """Fetch historical OHLCV data from OKX."""
        ohlcv = self.okx.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    def calculate_indicators(self, df):
        """Calculate RSI, CCI, Bollinger Bands, and EMA 200."""
        df['rsi'] = self.calculate_rsi(df['close'], period=14)
        df['cci'] = self.calculate_cci(df, period=20)
        df['ema_200'] = df['close'].ewm(span=200).mean()
        df['bollinger_mid'] = df['close'].rolling(window=20).mean()
        df['bollinger_std'] = df['close'].rolling(window=20).std()
        df['bollinger_upper'] = df['bollinger_mid'] + (df['bollinger_std'] * 2)
        df['bollinger_lower'] = df['bollinger_mid'] - (df['bollinger_std'] * 2)
        return df

    @staticmethod
    def calculate_rsi(series, period):
        """Calculate the Relative Strength Index (RSI)."""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def calculate_cci(df, period):
        """Calculate the Commodity Channel Index (CCI)."""
        tp = (df['high'] + df['low'] + df['close']) / 3
        ma = tp.rolling(window=period).mean()
        md = tp.rolling(window=period).apply(lambda x: np.fabs(x - x.mean()).mean())
        cci = (tp - ma) / (0.015 * md)
        return cci

    def determine_signal(self, df):
        """Determine buy/sell signals based on indicators."""
        latest = df.iloc[-1]
        previous = df.iloc[-2]

        if (
            latest['rsi'] < 30
            and latest['cci'] < -100
            and latest['close'] < latest['bollinger_lower']
            and latest['close'] > latest['ema_200']
        ):
            return 'buy'

        if (
            latest['rsi'] > 70
            and latest['cci'] > 100
            and latest['close'] > latest['bollinger_upper']
            and latest['close'] < latest['ema_200']
        ):
            return 'sell'

        return 'hold'

    def execute_trade(self, symbol, signal, amount):
        """Execute a trade on OKX."""
        if signal == 'buy':
            order = self.okx.create_market_buy_order(symbol, amount)
            print(f"Buy order executed: {order}")
        elif signal == 'sell':
            order = self.okx.create_market_sell_order(symbol, amount)
            print(f"Sell order executed: {order}")
        else:
            print("No trade executed.")

    def run(self, symbol: str, timeframe: str = '1h', amount: float = 0.001):
        """Fetch data, calculate signals, and execute trades."""
        df = self.fetch_historical_data(symbol, timeframe)
        df = self.calculate_indicators(df)
        signal = self.determine_signal(df)
        self.execute_trade(symbol, signal, amount)
