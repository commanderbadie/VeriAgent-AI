"""Scenario data structure for ML training."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class ScenarioLabel(str, Enum):
    """Binary label for scenario safety."""

    SAFE = "SAFE"
    UNSAFE = "UNSAFE"


@dataclass(frozen=True, slots=True)
class BehavioralFeatures:
    """Behavioral features extracted from action patterns.
    
    These features focus on uncertain signals that require learning,
    NOT direct answers like 'permission_denied' or 'policy_violated'.
    """

    # Action characteristics
    tool_sensitivity: str  # "LOW", "MEDIUM", "HIGH"
    has_amount: bool
    amount_log: float | None  # log(amount) if has_amount else None
    num_parameters: int
    
    # Sequence patterns
    tool_call_count: int  # Total calls this session
    same_action_count: int  # Times this specific action was called
    retry_count: int  # Immediate retries of failed action
    previous_failure_count: int  # Failed actions in session
    
    # Temporal patterns
    seconds_since_last_action: float | None
    is_rapid_sequence: bool  # < 5 seconds since last action
    
    # Context signals
    action_frequency: int  # How many times this action appears in session
    sequence_anomaly_score: float  # 0-1, higher = more anomalous
    context_action_match: float  # 0-1, semantic match between context and action
    
    # User context
    user_role: str  # "ADMIN", "SUPPORT", "GUEST"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, handling None values."""
        return {k: v for k, v in asdict(self).items()}


@dataclass(frozen=True, slots=True)
class Scenario:
    """A single training scenario with features and label.
    
    Design principles:
    - Unique scenario_id
    - Grouped by scenario_family for split control
    - No target leakage features
    - Labels have explicit reasoning
    """

    scenario_id: str
    scenario_family: str  # Group related scenarios
    session_id: str
    
    # Proposed action
    action: str
    user_role: str
    parameters: dict[str, Any]
    
    # Behavioral features (NO direct answer features)
    behavioral_features: BehavioralFeatures
    
    # Ground truth
    label: ScenarioLabel
    label_reason: str
    
    # Metadata
    split: str = "train"  # "train", "validation", "test", "adversarial"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d["label"] = self.label.value
        d["behavioral_features"] = self.behavioral_features.to_dict()
        return d
    
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Scenario:
        """Create scenario from dictionary."""
        features_dict = d.pop("behavioral_features")
        features = BehavioralFeatures(**features_dict)
        
        label = ScenarioLabel(d.pop("label"))
        
        return cls(
            behavioral_features=features,
            label=label,
            **d
        )
    
    def validate(self) -> list[str]:
        """Validate scenario data. Returns list of errors (empty if valid)."""
        errors = []
        
        # Check required fields
        if not self.scenario_id:
            errors.append("scenario_id is empty")
        if not self.scenario_family:
            errors.append("scenario_family is empty")
        if not self.session_id:
            errors.append("session_id is empty")
        if not self.action:
            errors.append("action is empty")
        if not self.label_reason:
            errors.append("label_reason is empty")
        
        # Check no negative counts
        features = self.behavioral_features
        if features.tool_call_count < 0:
            errors.append("tool_call_count cannot be negative")
        if features.same_action_count < 0:
            errors.append("same_action_count cannot be negative")
        if features.retry_count < 0:
            errors.append("retry_count cannot be negative")
        if features.previous_failure_count < 0:
            errors.append("previous_failure_count cannot be negative")
        if features.action_frequency < 0:
            errors.append("action_frequency cannot be negative")
        if features.num_parameters < 0:
            errors.append("num_parameters cannot be negative")
        
        # Check bounded scores
        if not 0 <= features.sequence_anomaly_score <= 1:
            errors.append("sequence_anomaly_score must be in [0, 1]")
        if not 0 <= features.context_action_match <= 1:
            errors.append("context_action_match must be in [0, 1]")
        
        # Check temporal consistency
        if features.seconds_since_last_action is not None:
            if features.seconds_since_last_action < 0:
                errors.append("seconds_since_last_action cannot be negative")
        
        # Check amount consistency
        if features.has_amount and features.amount_log is None:
            errors.append("has_amount=True but amount_log is None")
        if not features.has_amount and features.amount_log is not None:
            errors.append("has_amount=False but amount_log is not None")
        
        # Check rapid sequence consistency
        if features.is_rapid_sequence:
            if features.seconds_since_last_action is None:
                errors.append("is_rapid_sequence=True but no seconds_since_last_action")
            elif features.seconds_since_last_action >= 5:
                errors.append("is_rapid_sequence=True but seconds_since_last_action >= 5")
        
        # Check logical constraints
        if features.same_action_count > features.tool_call_count:
            errors.append("same_action_count cannot exceed tool_call_count")
        if features.retry_count > features.previous_failure_count:
            errors.append("retry_count cannot exceed previous_failure_count")
        
        # Check no prohibited leakage features
        prohibited = [
            "permission_denied", "policy_violated", "expected_decision",
            "is_unsafe", "should_block", "rule_result", "final_decision",
            "verifier_decision"
        ]
        for key in self.parameters.keys():
            if key in prohibited:
                errors.append(f"Prohibited leakage feature in parameters: {key}")
        
        return errors
