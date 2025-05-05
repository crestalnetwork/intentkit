import json
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Dict, Optional

from langchain_core.language_models import LanguageModelLike
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String, func, select

from models.app_setting import AppSetting
from models.base import Base
from models.db import get_session
from models.redis import get_redis

_credit_per_usdc = None


class LLMProvider(str, Enum):
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    XAI = "xai"
    ETERNAL = "eternal"
    REIGENT = "reigent"


class LLMModelInfoTable(Base):
    """Database table model for LLM model information."""

    __tablename__ = "llm_models"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    provider = Column(String, nullable=False)  # Stored as string enum value
    input_price = Column(
        Numeric(22, 4), nullable=False
    )  # Price per 1M input tokens in USD
    output_price = Column(
        Numeric(22, 4), nullable=False
    )  # Price per 1M output tokens in USD
    context_length = Column(Integer, nullable=False)  # Maximum context length in tokens
    output_length = Column(Integer, nullable=False)  # Maximum output length in tokens
    intelligence = Column(Integer, nullable=False)  # Intelligence rating from 1-5
    speed = Column(Integer, nullable=False)  # Speed rating from 1-5
    supports_image_input = Column(Boolean, nullable=False, default=False)
    supports_skill_calls = Column(Boolean, nullable=False, default=False)
    supports_structured_output = Column(Boolean, nullable=False, default=False)
    has_reasoning = Column(Boolean, nullable=False, default=False)
    supports_temperature = Column(Boolean, nullable=False, default=True)
    supports_frequency_penalty = Column(Boolean, nullable=False, default=True)
    supports_presence_penalty = Column(Boolean, nullable=False, default=True)
    api_base = Column(String, nullable=True)  # Custom API base URL
    timeout = Column(Integer, nullable=False, default=180)  # Default timeout in seconds
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class LLMModelInfo(BaseModel):
    """Information about an LLM model."""

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
        json_encoders={datetime: lambda v: v.isoformat(timespec="milliseconds")},
    )

    id: str
    name: str
    provider: LLMProvider
    input_price: Decimal  # Price per 1M input tokens in USD
    output_price: Decimal  # Price per 1M output tokens in USD
    context_length: int  # Maximum context length in tokens
    output_length: int  # Maximum output length in tokens
    intelligence: int = Field(ge=1, le=5)  # Intelligence rating from 1-5
    speed: int = Field(ge=1, le=5)  # Speed rating from 1-5
    supports_image_input: bool = False  # Whether the model supports image inputs
    supports_skill_calls: bool = False  # Whether the model supports skill/tool calls
    supports_structured_output: bool = (
        False  # Whether the model supports structured output
    )
    has_reasoning: bool = False  # Whether the model has strong reasoning capabilities
    supports_temperature: bool = (
        True  # Whether the model supports temperature parameter
    )
    supports_frequency_penalty: bool = (
        True  # Whether the model supports frequency_penalty parameter
    )
    supports_presence_penalty: bool = (
        True  # Whether the model supports presence_penalty parameter
    )
    api_base: Optional[str] = (
        None  # Custom API base URL if not using provider's default
    )
    timeout: int = 180  # Default timeout in seconds
    created_at: Annotated[
        datetime,
        Field(
            description="Timestamp when this data was created",
            default=datetime.now(timezone.utc),
        ),
    ]
    updated_at: Annotated[
        datetime,
        Field(
            description="Timestamp when this data was updated",
            default=datetime.now(timezone.utc),
        ),
    ]

    @staticmethod
    async def get(model_id: str) -> Optional["LLMModelInfo"]:
        """Get a model by ID with Redis caching.

        The model info is cached in Redis for 3 minutes.

        Args:
            model_id: ID of the model to retrieve

        Returns:
            LLMModelInfo: The model info if found, None otherwise
        """
        # Redis cache key for model info
        cache_key = f"intentkit:llm_model:{model_id}"
        cache_ttl = 180  # 3 minutes in seconds

        # Try to get from Redis cache first
        redis = get_redis()
        cached_data = await redis.get(cache_key)

        if cached_data:
            # If found in cache, deserialize and return
            try:
                return LLMModelInfo.model_validate_json(cached_data)
            except (json.JSONDecodeError, TypeError):
                # If cache is corrupted, invalidate it
                await redis.delete(cache_key)

        # If not in cache or cache is invalid, get from database
        async with get_session() as session:
            # Query the database for the model
            stmt = select(LLMModelInfoTable).where(LLMModelInfoTable.id == model_id)
            model = await session.scalar(stmt)

            # If model exists in database, convert to LLMModelInfo model and cache it
            if model:
                # Convert provider string to enum
                model_info = LLMModelInfo.model_validate(model)

                # Cache the model in Redis
                await redis.set(
                    cache_key,
                    model_info.model_dump_json(),
                    ex=cache_ttl,
                )

                return model_info

        # If not found in database, check AVAILABLE_MODELS
        if model_id in AVAILABLE_MODELS:
            model_info = AVAILABLE_MODELS[model_id]

            # Cache the model in Redis
            await redis.set(cache_key, model_info.model_dump_json(), ex=cache_ttl)

            return model_info

        # Not found anywhere
        return None

    async def calculate_cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        global _credit_per_usdc
        if not _credit_per_usdc:
            _credit_per_usdc = (await AppSetting.payment()).credit_per_usdc
        """Calculate the cost for a given number of tokens."""
        input_cost = (
            _credit_per_usdc
            * Decimal(input_tokens)
            * self.input_price
            / Decimal(1000000)
        )
        output_cost = (
            _credit_per_usdc
            * Decimal(output_tokens)
            * self.output_price
            / Decimal(1000000)
        )
        return input_cost + output_cost


# Define all available models
AVAILABLE_MODELS = {
    # OpenAI models
    "gpt-4o": LLMModelInfo(
        id="gpt-4o",
        name="GPT-4o",
        provider=LLMProvider.OPENAI,
        input_price=Decimal("2.50"),  # per 1M input tokens
        output_price=Decimal("10.00"),  # per 1M output tokens
        context_length=128000,
        output_length=4096,
        intelligence=4,
        speed=3,
        supports_image_input=True,
        supports_skill_calls=True,
        supports_structured_output=True,
    ),
    "gpt-4o-mini": LLMModelInfo(
        id="gpt-4o-mini",
        name="GPT-4o Mini",
        provider=LLMProvider.OPENAI,
        input_price=Decimal("0.15"),  # per 1M input tokens
        output_price=Decimal("0.60"),  # per 1M output tokens
        context_length=128000,
        output_length=4096,
        intelligence=3,
        speed=4,
        supports_image_input=False,
        supports_skill_calls=True,
        supports_structured_output=True,
    ),
    "gpt-4.1-nano": LLMModelInfo(
        id="gpt-4.1-nano",
        name="GPT-4.1 Nano",
        provider=LLMProvider.OPENAI,
        input_price=Decimal("0.1"),  # per 1M input tokens
        output_price=Decimal("0.4"),  # per 1M output tokens
        context_length=128000,
        output_length=4096,
        intelligence=3,
        speed=5,
        supports_image_input=False,
        supports_skill_calls=True,
        supports_structured_output=True,
    ),
    "gpt-4.1-mini": LLMModelInfo(
        id="gpt-4.1-mini",
        name="GPT-4.1 Mini",
        provider=LLMProvider.OPENAI,
        input_price=Decimal("0.4"),  # per 1M input tokens
        output_price=Decimal("1.6"),  # per 1M output tokens
        context_length=128000,
        output_length=4096,
        intelligence=4,
        speed=4,
        supports_image_input=False,
        supports_skill_calls=True,
        supports_structured_output=True,
    ),
    "gpt-4.1": LLMModelInfo(
        id="gpt-4.1",
        name="GPT-4.1",
        provider=LLMProvider.OPENAI,
        input_price=Decimal("2.00"),  # per 1M input tokens
        output_price=Decimal("8.00"),  # per 1M output tokens
        context_length=128000,
        output_length=4096,
        intelligence=5,
        speed=3,
        supports_image_input=True,
        supports_skill_calls=True,
        supports_structured_output=True,
    ),
    "o4-mini": LLMModelInfo(
        id="o4-mini",
        name="OpenAI o4-mini",
        provider=LLMProvider.OPENAI,
        input_price=Decimal("1.10"),  # per 1M input tokens
        output_price=Decimal("4.40"),  # per 1M output tokens
        context_length=128000,
        output_length=4096,
        intelligence=4,
        speed=3,
        supports_image_input=False,
        supports_skill_calls=True,
        supports_structured_output=True,
        has_reasoning=True,  # Has strong reasoning capabilities
    ),
    # Deepseek models
    "deepseek-chat": LLMModelInfo(
        id="deepseek-chat",
        name="Deepseek V3 (0324)",
        provider=LLMProvider.DEEPSEEK,
        input_price=Decimal("0.27"),
        output_price=Decimal("1.10"),
        context_length=60000,
        output_length=4096,
        intelligence=4,
        speed=3,
        supports_image_input=False,
        supports_skill_calls=True,
        supports_structured_output=True,
        api_base="https://api.deepseek.com",
        timeout=300,
    ),
    "deepseek-reasoner": LLMModelInfo(
        id="deepseek-reasoner",
        name="Deepseek R1",
        provider=LLMProvider.DEEPSEEK,
        input_price=Decimal("0.55"),
        output_price=Decimal("2.19"),
        context_length=60000,
        output_length=4096,
        intelligence=4,
        speed=2,
        supports_image_input=False,
        supports_skill_calls=True,
        supports_structured_output=True,
        has_reasoning=True,  # Has strong reasoning capabilities
        api_base="https://api.deepseek.com",
        timeout=300,
    ),
    # XAI models
    "grok-2": LLMModelInfo(
        id="grok-2",
        name="Grok 2",
        provider=LLMProvider.XAI,
        input_price=Decimal("2"),
        output_price=Decimal("10"),
        context_length=120000,
        output_length=4096,
        intelligence=3,
        speed=3,
        supports_image_input=False,
        supports_skill_calls=True,
        supports_structured_output=True,
        timeout=180,
    ),
    "grok-3": LLMModelInfo(
        id="grok-3",
        name="Grok 3",
        provider=LLMProvider.XAI,
        input_price=Decimal("3"),
        output_price=Decimal("15"),
        context_length=131072,
        output_length=4096,
        intelligence=5,
        speed=3,
        supports_image_input=False,
        supports_skill_calls=True,
        supports_structured_output=True,
        timeout=180,
    ),
    "grok-3-mini": LLMModelInfo(
        id="grok-3-mini",
        name="Grok 3 Mini",
        provider=LLMProvider.XAI,
        input_price=Decimal("0.3"),
        output_price=Decimal("0.5"),
        context_length=131072,
        output_length=4096,
        intelligence=5,
        speed=3,
        supports_image_input=False,
        supports_skill_calls=True,
        supports_structured_output=True,
        has_reasoning=True,  # Has strong reasoning capabilities
        supports_frequency_penalty=False,
        supports_presence_penalty=False,  # Grok-3-mini doesn't support presence_penalty
        timeout=180,
    ),
    # Eternal AI models
    "eternalai": LLMModelInfo(
        id="eternalai",
        name="Eternal AI (Llama-3.3-70B)",
        provider=LLMProvider.ETERNAL,
        input_price=Decimal("0.25"),
        output_price=Decimal("0.75"),
        context_length=60000,
        output_length=4096,
        intelligence=4,
        speed=3,
        supports_image_input=False,
        supports_skill_calls=True,
        supports_structured_output=True,
        api_base="https://api.eternalai.org/v1",
        timeout=300,
    ),
    # Reigent models
    "reigent": LLMModelInfo(
        id="reigent",
        name="REI Network",
        provider=LLMProvider.REIGENT,
        input_price=Decimal("0.50"),  # Placeholder price, update with actual pricing
        output_price=Decimal("1.50"),  # Placeholder price, update with actual pricing
        context_length=32000,
        output_length=4096,
        intelligence=4,
        speed=3,
        supports_image_input=False,
        supports_skill_calls=True,
        supports_structured_output=True,
        supports_temperature=False,
        supports_frequency_penalty=False,
        supports_presence_penalty=False,
        api_base="https://api.reisearch.box/v1",
        timeout=300,
    ),
}


class LLMModel(BaseModel):
    """Base model for LLM configuration."""

    model_name: str
    temperature: float = 0.7
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0

    async def model_info(self) -> LLMModelInfo:
        """Get the model information with caching.

        First tries to get from cache, then database, then AVAILABLE_MODELS.
        Raises ValueError if model is not found anywhere.
        """
        model_info = await LLMModelInfo.get(self.model_name)
        if not model_info:
            raise ValueError(f"Unknown model: {self.model_name}")
        return model_info

    # This will be implemented by subclasses to return the appropriate LLM instance
    async def create_instance(self, config: Any) -> LanguageModelLike:
        """Create and return the LLM instance based on the configuration."""
        raise NotImplementedError("Subclasses must implement create_instance")

    async def get_token_limit(self) -> int:
        """Get the token limit for this model."""
        info = await self.model_info()
        return info.context_length

    async def calculate_cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        """Calculate the cost for a given number of tokens."""
        info = await self.model_info()
        return await info.calculate_cost(input_tokens, output_tokens)


class OpenAILLM(LLMModel):
    """OpenAI LLM configuration."""

    async def create_instance(self, config: Any) -> LanguageModelLike:
        """Create and return a ChatOpenAI instance."""
        from langchain_openai import ChatOpenAI

        info = await self.model_info()

        kwargs = {
            "model_name": self.model_name,
            "openai_api_key": config.openai_api_key,
            "timeout": info.timeout,
        }

        # Add optional parameters based on model support
        if info.supports_temperature:
            kwargs["temperature"] = self.temperature

        if info.supports_frequency_penalty:
            kwargs["frequency_penalty"] = self.frequency_penalty

        if info.supports_presence_penalty:
            kwargs["presence_penalty"] = self.presence_penalty

        if info.api_base:
            kwargs["openai_api_base"] = info.api_base

        return ChatOpenAI(**kwargs)


class DeepseekLLM(LLMModel):
    """Deepseek LLM configuration."""

    async def create_instance(self, config: Any) -> LanguageModelLike:
        """Create and return a ChatDeepseek instance."""

        from langchain_openai import ChatOpenAI

        info = await self.model_info()

        kwargs = {
            "model_name": self.model_name,
            "openai_api_key": config.deepseek_api_key,
            "timeout": info.timeout,
        }

        # Add optional parameters based on model support
        if info.supports_temperature:
            kwargs["temperature"] = self.temperature

        if info.supports_frequency_penalty:
            kwargs["frequency_penalty"] = self.frequency_penalty

        if info.supports_presence_penalty:
            kwargs["presence_penalty"] = self.presence_penalty

        if info.api_base:
            kwargs["openai_api_base"] = info.api_base

        return ChatOpenAI(**kwargs)


class XAILLM(LLMModel):
    """XAI (Grok) LLM configuration."""

    async def create_instance(self, config: Any) -> LanguageModelLike:
        """Create and return a ChatXAI instance."""

        from langchain_xai import ChatXAI

        info = await self.model_info()

        kwargs = {
            "model_name": self.model_name,
            "xai_api_key": config.xai_api_key,
            "timeout": info.timeout,
        }

        # Add optional parameters based on model support
        if info.supports_temperature:
            kwargs["temperature"] = self.temperature

        if info.supports_frequency_penalty:
            kwargs["frequency_penalty"] = self.frequency_penalty

        if info.supports_presence_penalty:
            kwargs["presence_penalty"] = self.presence_penalty

        return ChatXAI(**kwargs)


class EternalLLM(LLMModel):
    """Eternal AI LLM configuration."""

    async def create_instance(self, config: Any) -> LanguageModelLike:
        """Create and return a ChatOpenAI instance configured for Eternal AI."""
        from langchain_openai import ChatOpenAI

        info = await self.model_info()

        # Override model name for Eternal AI
        actual_model = "unsloth/Llama-3.3-70B-Instruct-bnb-4bit"

        kwargs = {
            "model_name": actual_model,
            "openai_api_key": config.eternal_api_key,
            "openai_api_base": info.api_base,
            "timeout": info.timeout,
        }

        # Add optional parameters based on model support
        if info.supports_temperature:
            kwargs["temperature"] = self.temperature

        if info.supports_frequency_penalty:
            kwargs["frequency_penalty"] = self.frequency_penalty

        if info.supports_presence_penalty:
            kwargs["presence_penalty"] = self.presence_penalty

        return ChatOpenAI(**kwargs)


class ReigentLLM(LLMModel):
    """Reigent LLM configuration."""

    async def create_instance(self, config: Any) -> LanguageModelLike:
        """Create and return a ChatOpenAI instance configured for Reigent."""
        from langchain_openai import ChatOpenAI

        info = await self.model_info()

        kwargs = {
            "openai_api_key": config.reigent_api_key,
            "openai_api_base": "https://api.reisearch.box/v1",
            "timeout": info.timeout,
            "model_kwargs": {
                # Override any specific parameters required for Reigent API
                # The Reigent API requires 'tools' instead of 'functions' and might have some specific formatting requirements
            },
        }

        return ChatOpenAI(**kwargs)


# Factory function to create the appropriate LLM model based on the model name
def create_llm_model(
    model_name: str,
    temperature: float = 0.7,
    frequency_penalty: float = 0.0,
    presence_penalty: float = 0.0,
) -> LLMModel:
    """
    Create an LLM model instance based on the model name.

    Args:
        model_name: The name of the model to use
        temperature: The temperature parameter for the model
        frequency_penalty: The frequency penalty parameter for the model
        presence_penalty: The presence penalty parameter for the model

    Returns:
        An instance of a subclass of LLMModel
    """
    if model_name not in AVAILABLE_MODELS:
        raise ValueError(f"Unknown model: {model_name}")

    base_params = {
        "model_name": model_name,
        "temperature": temperature,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
    }

    provider = AVAILABLE_MODELS[model_name].provider

    if provider == LLMProvider.DEEPSEEK:
        return DeepseekLLM(**base_params)
    elif provider == LLMProvider.XAI:
        return XAILLM(**base_params)
    elif provider == LLMProvider.ETERNAL:
        return EternalLLM(**base_params)
    elif provider == LLMProvider.REIGENT:
        return ReigentLLM(**base_params)
    else:
        # Default to OpenAI
        return OpenAILLM(**base_params)


# Utility functions
def get_available_models() -> Dict[str, LLMModelInfo]:
    """Get all available models."""
    return AVAILABLE_MODELS


def get_model_info(model_name: str) -> LLMModelInfo:
    """Get information about a specific model."""
    if model_name not in AVAILABLE_MODELS:
        raise ValueError(f"Unknown model: {model_name}")
    return AVAILABLE_MODELS[model_name]


async def get_model_cost(
    model_name: str, input_tokens: int, output_tokens: int
) -> Decimal:
    """Get the cost of a specific model."""
    info = get_model_info(model_name)
    return await info.calculate_cost(input_tokens, output_tokens)
