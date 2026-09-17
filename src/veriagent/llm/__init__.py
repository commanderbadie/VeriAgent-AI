"""LLM adapters for model-independent agent implementation."""

from .base import BaseLLM, LLMError, LLMResponse, LLMTimeout
from .fake import FakeLLM
from .ollama import OllamaLLM, ollama_available

__all__ = [
    "BaseLLM",
    "LLMResponse",
    "LLMError",
    "LLMTimeout",
    "FakeLLM",
    "OllamaLLM",
    "ollama_available",
]
