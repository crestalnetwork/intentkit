from pydantic import BaseModel
from typing import Optional

class DictoInput(BaseModel):
    word: str
    lang: Optional[str] = "en"

class DictoOutput(BaseModel):
    result: str
