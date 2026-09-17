"""LLM adapters for model-independent agent implementation."""

from .base import BaseLLM, LLMError, LLMResponse, LLMTimeout
from .fake import FakeLLM

__all__ = ["BaseLLM", "LLMResponse", "LLMError", "LLMTimeout", "FakeLLM"]
