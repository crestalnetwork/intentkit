# Creating Custom Skills

## Overview

IntentKit skills are Python modules that extend agent capabilities. Each skill is a LangChain tool that can be dynamically loaded based on agent configuration.

## Skill Structure

A basic skill consists of:
1. Tool implementation
2. Registration in the skill system
3. Configuration options ( optional )

### Example Skill

```python
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

class WeatherInput(BaseModel):
    """Input for weather skill."""
    location: str = Field(..., description="City name or coordinates")
    unit: str = Field("celsius", description="Temperature unit (celsius/fahrenheit)")

class WeatherSkill(BaseTool):
    name = "get_weather"
    description = "Get current weather for a location"
    args_schema = WeatherInput
    
    def _run(self, location: str, unit: str = "celsius") -> str:
        """Implementation of weather checking logic."""
        # Your implementation here
        return f"Weather in {location}: 20°{unit[0].upper()}"
    
    async def _arun(self, location: str, unit: str = "celsius") -> str:
        """Async implementation (optional)."""
        return await asyncio.to_thread(self._run, location, unit)
```

## Registering Skills

Skills must be registered in `skill/__init__.py`:

```python
from .weather import WeatherSkill

def get_crestal_skill(name: str) -> BaseTool:
    """Get a skill by name."""
    skills = {
        "weather": WeatherSkill(),
        # Add more skills here
    }
    return skills.get(name)
```

## Skill Sets

Skill sets are collections of related skills with shared configuration:

```python
def get_skill_set(name: str, config: dict) -> list[BaseTool]:
    """Get a set of skills with configuration."""
    if name == "weather_set":
        return [
            WeatherSkill(),
            TemperatureAlertSkill(config.get("threshold")),
            # More related skills
        ]
    return []
```

## Best Practices

1. **Input Validation**
   - Use Pydantic models for input validation
   - Provide clear field descriptions
   - Set sensible defaults

2. **Error Handling**
   - Handle external service errors gracefully
   - Provide meaningful error messages
   - Log errors appropriately

3. **Documentation**
   - Document skill purpose and usage
   - Include example inputs and outputs
   - List any required credentials or setup

4. **Testing**
   - Write unit tests for skill logic
   - Mock external service calls
   - Test error conditions

5. **Performance**
   - Implement async versions when possible
   - Cache results when appropriate
   - Handle rate limits

## Configuration

Skills can be enabled per agent in the agent configuration:

```json
{
  "id": "weather-agent",
  "crestal_skills": ["weather"],
  "skill_sets": {
    "weather_set": {
      "threshold": 30
    }
  }
}
```
