"""BlockRun LangChain ChatModel wrapper.

Provides LangChain-compatible ChatModel that uses BlockRun.AI's x402 micropayment
gateway to access multiple LLM providers (OpenAI, Anthropic, Google, DeepSeek).
"""

import os
from typing import Any, Iterator, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from intentkit.config.config import config


class BlockRunChat(BaseChatModel):
    """LangChain ChatModel for BlockRun.AI x402 micropayment gateway.

    This wrapper uses the blockrun_llm SDK to handle x402 payment flow
    and provides a standard LangChain interface.

    Example:
        chat = BlockRunChat(model="anthropic/claude-sonnet-4", max_tokens=4096)
        response = chat.invoke("Hello!")
    """

    model: str = "openai/gpt-4o-mini"
    max_tokens: int = 4096
    temperature: float = 0.7

    _client: Any = None

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._init_client()

    def _init_client(self) -> None:
        """Initialize the BlockRun LLM client."""
        from blockrun_llm import LLMClient

        private_key = config.blockrun_wallet_key
        if not private_key:
            private_key = os.getenv("BLOCKRUN_WALLET_KEY")

        if not private_key:
            raise ValueError(
                "BlockRun wallet key not found. Set BLOCKRUN_WALLET_KEY env var "
                "or config.blockrun_wallet_key"
            )

        self._client = LLMClient(private_key=private_key)

    @property
    def _llm_type(self) -> str:
        return "blockrun"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

    def _convert_messages(self, messages: List[BaseMessage]) -> List[dict]:
        """Convert LangChain messages to BlockRun format."""
        converted = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                converted.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                converted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                converted.append({"role": "assistant", "content": msg.content})
            else:
                # Default to user role for unknown message types
                converted.append({"role": "user", "content": str(msg.content)})
        return converted

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate a response using BlockRun API."""
        converted_messages = self._convert_messages(messages)

        # Call BlockRun API
        response = self._client.chat_completion(
            model=self.model,
            messages=converted_messages,
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            temperature=kwargs.get("temperature", self.temperature),
        )

        # Extract response content
        content = response.choices[0].message.content

        # Create ChatGeneration
        generation = ChatGeneration(
            message=AIMessage(content=content),
            generation_info={
                "model": self.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                }
            }
        )

        return ChatResult(generations=[generation])

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Async generate - currently delegates to sync version."""
        # TODO: Use AsyncLLMClient when available
        return self._generate(messages, stop, run_manager, **kwargs)
