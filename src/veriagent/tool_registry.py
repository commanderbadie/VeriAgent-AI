"""Tool registry for managing and allowlisting business operations.

Only registered tools can be executed by the SecureExecutor.
This prevents agents from calling arbitrary functions or bypassing verification.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class ToolNotFoundError(Exception):
    """Requested tool is not registered."""


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Metadata and callable for a registered tool."""

    name: str
    callable: Callable[..., Any]
    description: str
    risk_level: str  # "LOW", "MEDIUM", "HIGH"


class ToolRegistry:
    """Allowlist of tools that agents are permitted to call through verification."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        callable: Callable[..., Any],
        description: str,
        risk_level: str = "MEDIUM",
    ) -> None:
        """Register a tool that can be called through the executor.

        Args:
            name: Unique tool identifier (matches ProposedAction.tool)
            callable: The actual function to call
            description: Human-readable purpose
            risk_level: "LOW", "MEDIUM", or "HIGH"
        """
        if risk_level not in {"LOW", "MEDIUM", "HIGH"}:
            raise ValueError(f"Invalid risk level: {risk_level}")

        if name in self._tools:
            raise ValueError(f"Tool {name} is already registered")

        self._tools[name] = ToolDefinition(
            name=name,
            callable=callable,
            description=description,
            risk_level=risk_level,
        )

    def get(self, name: str) -> ToolDefinition:
        """Retrieve a registered tool definition."""
        if name not in self._tools:
            raise ToolNotFoundError(f"Tool {name} is not registered")
        return self._tools[name]

    def is_registered(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def list_tools(self) -> list[ToolDefinition]:
        """List all registered tools."""
        return list(self._tools.values())

    def unregister(self, name: str) -> None:
        """Remove a tool from the registry (for testing/maintenance)."""
        if name in self._tools:
            del self._tools[name]
