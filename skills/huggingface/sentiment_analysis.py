from typing import Type
from pydantic import BaseModel, Field
from skills.huggingface.base import HuggingFaceBaseTool
from transformers import pipeline

class SentimentAnalysisInput(BaseModel):
    text: str = Field(description="Text to analyze sentiment for")

class SentimentAnalysis(HuggingFaceBaseTool):
    name: str = "sentiment_analysis"
    description: str = "Analyze sentiment of a given text using HuggingFace Transformers"
    args_schema: Type[BaseModel] = SentimentAnalysisInput

    _analyzer = pipeline("sentiment-analysis")

    async def _arun(self, text: str, **kwargs) -> str:
        try:
            result = self._analyzer(text)[0]
            return f"Sentiment: {result['label']} with score {result['score']:.2f}"
        except Exception as e:
            return f"Failed to analyze sentiment: {str(e)}"

