from intentkit.agent.skills.base import BaseSkill
from .weatherpulse_skill import FetchWeatherForecast, FetchWeatherAlerts


class WeatherPulseSkill(BaseSkill):
    """
    WeatherPulseSkill adalah kumpulan fungsi untuk mendapatkan prakiraan cuaca dan peringatan cuaca
    dari sumber API eksternal.
    """

    def __init__(self, config):
        super().__init__(config=config)

        self.add_state("fetch_weather_forecast", FetchWeatherForecast(config))
        self.add_state("fetch_weather_alerts", FetchWeatherAlerts(config))
