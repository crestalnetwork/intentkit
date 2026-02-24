# skills/currency_conversion/exchange_rate_api.py
import requests
from .base import CurrencyConversionSkill

class ExchangeRateAPISkill(CurrencyConversionSkill):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        url = f"https://v6.exchangerate-api.com/v6/{self.api_key}/pair/{from_currency}/{to_currency}"
        response = requests.get(url)
        data = response.json()

        if response.status_code != 200 or 'conversion_rate' not in data:
            raise ValueError("Failed to retrieve conversion rate.")

        rate = data['conversion_rate']
        return amount * rate
