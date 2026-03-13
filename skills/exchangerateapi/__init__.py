# skills/currency_conversion/__init__.py
from .exchange_rate_api import ExchangeRateAPISkill

def get_skills(config):
    return [
        ExchangeRateAPISkill(api_key=config["api_key"])
    ]
