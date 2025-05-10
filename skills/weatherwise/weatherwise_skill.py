from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableConfig
import requests

from intentkit.core.tool import IntentKitTool
from intentkit.core.skill_config import SkillConfig
from intentkit.core.skill_states import SkillStates

class Config(SkillConfig):
    states: SkillStates
    api_key: str

class WeatherWiseInput(BaseModel):
    location: str = Field(description="Location (city name or city,country_code) to fetch weather for.")

class WeatherWise(IntentKitTool):
    name = "analyze_weather"
    description = "Get and analyze current weather conditions for a given location."
    input_schema = WeatherWiseInput

    def __init__(self, config: Config):
        self.api_key = config.api_key
        super().__init__()

    async def _arun(self, config: RunnableConfig, location: str) -> str:
        context = self.context_from_config(config)
        url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={self.api_key}&units=metric"
        response = requests.get(url)
        if response.status_code != 200:
            return f"Failed to fetch weather for {location}. Please check the location and try again."

        data = response.json()
        desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        humidity = data["main"]["humidity"]

        return (
            f"Current weather in {location}:\n"
            f"- Condition: {desc}\n"
            f"- Temperature: {temp}°C\n"
            f"- Humidity: {humidity}%\n"
            f"This information may help you plan your day better!"
        )
