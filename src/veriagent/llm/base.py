"""Model-independent LLM interface.

This interface allows VeriAgent to work with any LLM backend
without coupling to a specific provider or implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class LLMError(Exception):
    """LLM request failed."""


class LLMTimeout(LLMError):
    """LLM request timed out."""


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Response from an LLM."""

    content: str  # Raw text response
    model: str  # Model identifier
    metadata: dict[str, Any] | None = None  # Optional metadata (tokens, latency, etc.)


class BaseLLM(ABC):
    """Abstract base class for LLM adapters.

    All LLM implementations must:
    1. Accept a prompt string
    2. Return raw text response
    3. Raise LLMError on failure
    4. Raise LLMTimeout on timeout
    5. Never execute tools directly
    6. Never access database directly
    7. Never bypass verification
    """

    @abstractmethod
    def generate(self, prompt: str, timeout: float = 30.0) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            prompt: Input prompt for the model
            timeout: Maximum seconds to wait (default 30)

        Returns:
            LLMResponse with raw text content

        Raises:
            LLMTimeout: If request exceeds timeout
            LLMError: If request fails for any other reason
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier."""
        pass
