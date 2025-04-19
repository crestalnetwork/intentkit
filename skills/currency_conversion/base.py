# skills/currency_conversion/base.py
from intentkit.skills.base_skill import BaseSkill

class CurrencyConversionSkill(BaseSkill):
    def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        raise NotImplementedError("This method must be implemented by subclasses.")
