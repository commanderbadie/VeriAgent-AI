"""Domain models shared by the agent and verification layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Decision(str, Enum):
    """Possible outcomes for a proposed action."""

    ALLOW = "ALLOW"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


@dataclass(frozen=True, slots=True)
class ProposedAction:
    """A structured action proposed by an agent but not yet executed."""

    action: str
    user_role: str
    parameters: dict[str, Any] = field(default_factory=dict)
    tool: str | None = None


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Deterministic verification decision and human-readable evidence."""

    decision: Decision
    reasons: tuple[str, ...]
    checks: dict[str, bool]
