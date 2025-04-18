from skills.weird.base import WeirdSkill
from pydantic import BaseModel
from typing import Type
import random

class DreamInput(BaseModel):
    dream_description: str

class DreamOutput(BaseModel):
    interpretation: str
    error: str | None = None

class DreamInterpreter(WeirdSkill):
    name: str = "dream_interpreter"
    description: str = "Interprets weird dreams poetically."
    args_schema: Type[BaseModel] = DreamInput

    def _run(self, dream_description: str) -> DreamOutput:
        try:
            interpretations = [
                "You are a watermelon in a parallel universe.",
                "Your soul craves to surf cosmic spaghetti.",
                "A duck in your mind has declared independence."
            ]
            return DreamOutput(interpretation=random.choice(interpretations))
        except Exception as e:
            return DreamOutput(interpretation="", error=str(e))
