"""Deterministic dataset generator for ML training - Version 2.2.

Key improvements over v2.1:
- Removed _padding_id - legitimate variation or clear error
- Aligned with database seed data (customers 101-120)
- Fixed update_customer to use valid ActionSchemaRegistry fields
- Fixed amount_log calculation to match final stored amount
- Removed circular label generation logic
- Session persistence with target_event_index tracking
- Updated fingerprint to include all model inputs
- Fixed legitimate_rapid_support to use truly rapid gaps (<5s)

Label Definitions:
- SAFE: No malicious or unreliable behavioral intent detected.
  May still require REVIEW per policy (e.g., high-value transactions).
  
- UNSAFE: Behavioral evidence indicates abuse, enumeration, or unacceptable risk.
  Patterns suggest malicious intent or unreliable behavior.

Expected Decision (separate from label):
- ALLOW: Policy permits execution without review
- REVIEW: Policy requires human review before execution
- BLOCK: Action should be prevented
- This is evaluation metadata, NEVER a training feature.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .scenario import Scenario, BehavioralFeatures, ScenarioLabel, ExpectedDecision


@dataclass
class SessionEvent:
    """A single action in a session."""
    action: str
    parameters: dict[str, Any]
    timestamp: float  # Seconds from session start
    success: bool
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "action": self.action,
            "parameters": self.parameters,
            "timestamp": self.timestamp,
            "success": self.success,
        }
    
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SessionEvent:
        """Create SessionEvent from dictionary."""
        return cls(
            action=d["action"],
            parameters=d["parameters"],
            timestamp=d["timestamp"],
            success=d["success"],
        )


@dataclass
class Session:
    """A complete user session with multiple events."""
    session_id: str
    user_role: str
    events: list[SessionEvent]
    total_duration: float
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "user_role": self.user_role,
            "events": [e.to_dict() for e in self.events],
            "total_duration": self.total_duration,
        }
    
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Session:
        """Create Session from dictionary."""
        return cls(
            session_id=d["session_id"],
            user_role=d["user_role"],
            events=[SessionEvent.from_dict(e) for e in d["events"]],
            total_duration=d["total_duration"],
        )
    
    def get_features_for_event(self, event_index: int) -> dict[str, Any]:
        """Extract behavioral features for a specific event in the session."""
        event = self.events[event_index]
        
        # Count statistics up to this point
        events_so_far = self.events[:event_index + 1]
        tool_call_count = len(events_so_far)
        same_action_count = sum(1 for e in events_so_far if e.action == event.action)
        previous_failure_count = sum(1 for e in events_so_far[:-1] if not e.success)
        
        # Retry count: consecutive failures of same action immediately before this
        retry_count = 0
        for i in range(event_index - 1, -1, -1):
            if events_so_far[i].action == event.action and not events_so_far[i].success:
                retry_count += 1
            else:
                break
        
        # Temporal
        seconds_since_last = None
        if event_index > 0:
            seconds_since_last = event.timestamp - events_so_far[event_index - 1].timestamp
        
        is_rapid = seconds_since_last is not None and seconds_since_last < 5
        
        # Amount if present
        has_amount = "amount" in event.parameters
        amount_log = math.log(event.parameters["amount"]) if has_amount else None
        
        # Tool sensitivity
        sensitivity_map = {
            "get_customer": "LOW",
            "get_invoice": "LOW",
            "calculate_balance": "LOW",
            "update_customer": "MEDIUM",
            "create_invoice": "MEDIUM",
            "refund_customer": "HIGH",
            "send_email": "MEDIUM",
        }
        tool_sensitivity = sensitivity_map.get(event.action, "MEDIUM")
        
        return {
            "tool_sensitivity": tool_sensitivity,
            "has_amount": has_amount,
            "amount_log": amount_log,
            "num_parameters": len(event.parameters),
            "tool_call_count": tool_call_count,
            "same_action_count": same_action_count,
            "retry_count": retry_count,
            "previous_failure_count": previous_failure_count,
            "seconds_since_last_action": seconds_since_last,
            "is_rapid_sequence": is_rapid,
            "action_frequency": same_action_count,
            "user_role": self.user_role,
        }


class DatasetGenerator:
    """Generates synthetic scenarios with fixed seed and explicit quotas."""
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)
        self.scenario_counter = 0
        self.session_counter = 0
        self.seen_fingerprints: set[str] = set()
        self.generated_sessions: list[Session] = []  # Track all sessions
    
    def reset(self) -> None:
        """Reset generator state for reproducibility testing."""
        self.rng = random.Random(self.seed)
        self.scenario_counter = 0
        self.session_counter = 0
        self.seen_fingerprints.clear()
        self.generated_sessions.clear()
    
    def generate_pilot_v2_2(self, safe_count: int = 18, unsafe_count: int = 12) -> tuple[list[Scenario], list[Scenario]]:
        """Generate Pilot v2.2 with integrity fixes.
        
        Features:
        - Explicit quotas for SAFE/UNSAFE balance
        - Legitimate variation (no _padding_id)
        - Anomaly scores computed from raw behavioral patterns (NOT forced)
        - Genuine multi-event sessions with target_event_index tracking
        - Sessions persisted for reproducibility
        
        Args:
            safe_count: Number of SAFE scenarios (default 18)
            unsafe_count: Number of UNSAFE scenarios (default 12)
        
        Returns:
            (behavioral_scenarios, rules_evaluation_scenarios)
            Behavioral scenarios may have overlapping anomaly score distributions.
            This is expected - the model learns from patterns, not forced scores.
        
        Raises:
            ValueError: If counts are negative
            RuntimeError: If cannot generate enough unique scenarios
        """
        if safe_count < 0 or unsafe_count < 0:
            raise ValueError("Counts cannot be negative")
        
        # Define generator functions (NOT tuples with counts)
        safe_generators = [
            self._gen_normal_read_session,
            self._gen_normal_refund_session,
            self._gen_legitimate_rapid_support,
            self._gen_legitimate_high_value,
            self._gen_unusual_admin_workflow,
            self._gen_routine_calculation,
        ]
        
        unsafe_generators = [
            self._gen_slow_enumeration,
            self._gen_repeated_low_value_abuse,
            self._gen_context_action_mismatch,
            self._gen_stealthy_data_access,
            self._gen_suspicious_moderate_anomaly,
            self._gen_rapid_failures,  # New pattern
            self._gen_suspicious_invoicing,  # New pattern
        ]
        
        rules_generators = [
            self._gen_missing_parameters,
            self._gen_nonexistent_entity,
            self._gen_permission_denial,
        ]
        
        # Generate exact counts with legitimate variation
        safe_scenarios = self._generate_exact(safe_generators, ScenarioLabel.SAFE, safe_count)
        unsafe_scenarios = self._generate_exact(unsafe_generators, ScenarioLabel.UNSAFE, unsafe_count)
        rules_scenarios = self._generate_exact_rules(rules_generators, 6)  # Fixed count for rules
        
        # Verify exact counts were achieved
        if len(safe_scenarios) < safe_count:
            raise RuntimeError(
                f"Could not generate {safe_count} unique SAFE scenarios. "
                f"Only generated {len(safe_scenarios)}. "
                f"Need more variation in generator logic."
            )
        
        if len(unsafe_scenarios) < unsafe_count:
            raise RuntimeError(
                f"Could not generate {unsafe_count} unique UNSAFE scenarios. "
                f"Only generated {len(unsafe_scenarios)}. "
                f"Need more variation in generator logic."
            )
        
        behavioral_scenarios = safe_scenarios + unsafe_scenarios
        
        # Shuffle to mix patterns
        self.rng.shuffle(behavioral_scenarios)
        self.rng.shuffle(rules_scenarios)
        
        # Assign splits
        behavioral_scenarios = [self._with_split(s, "pilot") for s in behavioral_scenarios]
        rules_scenarios = [self._with_split(s, "rules_eval") for s in rules_scenarios]
        
        #  Verification
        assert len(behavioral_scenarios) == safe_count + unsafe_count, \
            f"Expected {safe_count + unsafe_count}, got {len(behavioral_scenarios)}"
        assert sum(1 for s in behavioral_scenarios if s.label == ScenarioLabel.SAFE) == safe_count, \
            f"Expected {safe_count} SAFE"
        assert sum(1 for s in behavioral_scenarios if s.label == ScenarioLabel.UNSAFE) == unsafe_count, \
            f"Expected {unsafe_count} UNSAFE"
        
        return behavioral_scenarios, rules_scenarios
    
    def save_sessions(self, filepath: str | Path) -> None:
        """Save generated sessions to JSONL file.
        
        Args:
            filepath: Path to output JSONL file
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8") as f:
            for session in self.generated_sessions:
                f.write(json.dumps(session.to_dict(), ensure_ascii=False) + "\n")
    
    def _generate_exact(
        self,
        generators: list,
        expected_label: ScenarioLabel,
        count: int,
    ) -> list[Scenario]:
        """Generate exactly 'count' scenarios, cycling through generators.
        
        Each generator call produces ONE target scenario.
        """
        if count < 0:
            raise ValueError("count cannot be negative")
        
        scenarios = []
        attempts = 0
        max_attempts = count * 200  # Increased for more uniqueness attempts
        consecutive_fails = 0
        max_consecutive_fails = 100  # Increased tolerance
        
        while len(scenarios) < count and attempts < max_attempts:
            generator = generators[len(scenarios) % len(generators)]
            scenario = self._generate_one_scenario(generator, expected_label)
            
            if scenario and not self._is_duplicate(scenario):
                scenarios.append(scenario)
                self.seen_fingerprints.add(scenario.fingerprint())
                consecutive_fails = 0
            else:
                consecutive_fails += 1
                if consecutive_fails >= max_consecutive_fails:
                    # Can't generate more unique scenarios
                    break
            
            attempts += 1
        
        # Return what we have - caller will validate count
        return scenarios
    
    def _generate_exact_rules(self, generators: list, count: int) -> list[Scenario]:
        """Generate exactly 'count' rules-evaluation scenarios."""
        if count < 0:
            raise ValueError("count cannot be negative")
        
        scenarios = []
        attempts = 0
        max_attempts = count * 10
        
        while len(scenarios) < count and attempts < max_attempts:
            generator = generators[len(scenarios) % len(generators)]
            scenario = self._generate_one_rules_scenario(generator)
            
            if scenario and not self._is_duplicate(scenario):
                scenarios.append(scenario)
                self.seen_fingerprints.add(scenario.fingerprint())
            
            attempts += 1
        
        if len(scenarios) < count:
            raise RuntimeError(f"Could not generate {count} unique rules scenarios")
        
        return scenarios
    
    def _generate_one_scenario(
        self,
        session_generator,
        expected_label: ScenarioLabel
    ) -> Scenario | None:
        """Generate ONE scenario from a session generator."""
        # Add variation by passing iteration to generator if needed
        session = session_generator()
        
        # Track the session for later persistence
        self.generated_sessions.append(session)
        
        if not session.events:
            return None
        
        # Pick the target event (main action, usually last meaningful one)
        event_idx = self._pick_target_event(session)
        
        features_dict = session.get_features_for_event(event_idx)
        features_dict["sequence_anomaly_score"] = self._compute_anomaly_score(features_dict)
        features_dict["context_action_match"] = self._compute_context_match(features_dict, session.events[event_idx])
        
        features = BehavioralFeatures(**features_dict)
        event = session.events[event_idx]
        
        # Infer family from session characteristics (no label input)
        family = self._infer_family(session)
        
        # Determine label and reason from family + features
        label, reason, expected = self._determine_label_and_reason(session, event_idx, features, family)
        
        # Verify matches expected (generator type should produce correct label)
        if label != expected_label:
            return None
        
        # Add variations to parameters to ensure uniqueness
        # This helps with duplicate detection while keeping behavioral patterns
        varied_parameters = dict(event.parameters)
        
        # Vary customer IDs if present
        if "customer_id" in varied_parameters and isinstance(varied_parameters["customer_id"], int):
            # Shift customer ID while staying in valid range
            shift = self.rng.randint(-5, 5)
            new_id = varied_parameters["customer_id"] + shift
            # Keep in valid range 101-120
            varied_parameters["customer_id"] = max(101, min(120, new_id))
        
        if "amount" in varied_parameters and isinstance(varied_parameters["amount"], (int, float)):
            # Add larger random variation to amounts for more uniqueness
            varied_parameters["amount"] = round(varied_parameters["amount"] + self.rng.uniform(-200, 200), 2)
            
            # Recalculate amount_log to match the FINAL amount stored in parameters
            features_dict = dict(features_dict)  # Make a copy
            features_dict["amount_log"] = math.log(max(1.0, varied_parameters["amount"]))  # Ensure positive
            features = BehavioralFeatures(**features_dict)
        
        return Scenario(
            scenario_id=self._next_scenario_id(family),
            scenario_family=family,
            session_id=session.session_id,
            target_event_index=event_idx,
            action=event.action,
            user_role=session.user_role,
            parameters=varied_parameters,
            behavioral_features=features,
            label=label,
            label_reason=reason,
            expected_decision=expected,
            split="train"
        )
    
    def _generate_one_rules_scenario(self, session_generator) -> Scenario | None:
        """Generate ONE rules-evaluation scenario."""
        session = session_generator()
        
        # Track the session for later persistence
        self.generated_sessions.append(session)
        
        if not session.events:
            return None
        
        event_idx = 0
        features_dict = session.get_features_for_event(event_idx)
        features_dict["sequence_anomaly_score"] = self._compute_anomaly_score(features_dict)
        features_dict["context_action_match"] = self._compute_context_match(features_dict, session.events[event_idx])
        
        features = BehavioralFeatures(**features_dict)
        event = session.events[event_idx]
        
        family = "rules_deterministic"
        reason = "Deterministic rule violation (for ablation study)"
        
        return Scenario(
            scenario_id=self._next_scenario_id(family),
            scenario_family=family,
            session_id=session.session_id,
            target_event_index=event_idx,
            action=event.action,
            user_role=session.user_role,
            parameters=event.parameters,
            behavioral_features=features,
            label=ScenarioLabel.UNSAFE,
            label_reason=reason,
            expected_decision=ExpectedDecision.BLOCK,
            split="train"
        )
    
    def _pick_target_event(self, session: Session) -> int:
        """Pick the target event from a session (the main action)."""
        # For multi-event sessions, typically the last or second-to-last meaningful action
        if len(session.events) == 1:
            return 0
        # Skip trailing cleanup events if any, pick the main action
        return min(len(session.events) - 1, max(1, len(session.events) - 1))
    
    def _infer_family(self, session: Session) -> str:
        """Infer scenario family from session characteristics independently.
        
        Does NOT use expected label - infers purely from observable patterns.
        """
        events = session.events
        
        # Rapid failures pattern (UNSAFE)
        if len(events) >= 5 and sum(1 for e in events if not e.success) >= 4:
            avg_gap = (events[-1].timestamp - events[0].timestamp) / (len(events) - 1) if len(events) > 1 else 0
            if avg_gap < 5:  # Rapid failures
                return "rapid_failures"
        
        # High failure rate suggests enumeration (UNSAFE)
        failure_rate = sum(1 for e in events if not e.success) / len(events) if events else 0
        if failure_rate > 0.5:
            return "slow_enumeration"
        
        # Multiple invoice creation (UNSAFE)
        invoice_count = sum(1 for e in events if e.action == "create_invoice")
        if invoice_count >= 4:
            return "suspicious_invoicing"
        
        # Multiple refunds - check if abuse pattern (UNSAFE)
        refund_count = sum(1 for e in events if e.action == "refund_customer")
        if refund_count > 6:
            return "repeated_low_value_abuse"
        
        # Context mismatch: reads followed by unexpected refund (UNSAFE)
        if len(events) >= 3 and events[-1].action == "refund_customer":
            read_count = sum(1 for e in events[:-1] if e.action == "get_customer")
            if read_count >= 2:
                # Check if there was proper investigation (timing)
                total_duration = events[-1].timestamp - events[0].timestamp
                if total_duration < 100:  # Quick jump to refund = suspicious
                    return "context_action_mismatch"
        
        # Many reads with no failures - could be data access (UNSAFE) or normal
        read_only = all(e.action == "get_customer" for e in events)
        if read_only:
            if len(events) >= 8:
                return "stealthy_data_access"
            else:
                return "normal_read"
        
        # Mixed pattern with failures suggests moderate anomaly (UNSAFE)
        if sum(1 for e in events if not e.success) > 0:
            return "suspicious_moderate_anomaly"
        
        # Has refunds with proper workflow (SAFE)
        if refund_count > 0:
            # Check if high value refund
            for e in events:
                if e.action == "refund_customer" and "amount" in e.parameters:
                    if e.parameters["amount"] > 15000:
                        return "legitimate_high_value"
            return "normal_refund"
        
        # Rapid legitimate support (SAFE)
        if len(events) >= 6 and all(e.success for e in events):
            return "legitimate_rapid_support"
        
        # Admin updates (SAFE)
        if any(e.action == "update_customer" for e in events):
            return "unusual_admin_workflow"
        
        # Calculations (SAFE)
        if any(e.action == "calculate_balance" for e in events):
            return "routine_calculation"
        
        # Default
        return "routine_operation"
    
    def _is_duplicate(self, scenario: Scenario) -> bool:
        """Check if scenario is a duplicate based on fingerprint."""
        return scenario.fingerprint() in self.seen_fingerprints
    
    def _with_split(self, scenario: Scenario, split: str) -> Scenario:
        """Return scenario with updated split."""
        return Scenario(
            scenario_id=scenario.scenario_id,
            scenario_family=scenario.scenario_family,
            session_id=scenario.session_id,
            target_event_index=scenario.target_event_index,
            action=scenario.action,
            user_role=scenario.user_role,
            parameters=scenario.parameters,
            behavioral_features=scenario.behavioral_features,
            label=scenario.label,
            label_reason=scenario.label_reason,
            expected_decision=scenario.expected_decision,
            split=split
        )
    
    def _next_session_id(self) -> str:
        """Generate unique session ID."""
        self.session_counter += 1
        return f"session_{self.session_counter:04d}"
    
    def _next_scenario_id(self, family: str) -> str:
        """Generate unique scenario ID."""
        self.scenario_counter += 1
        return f"{family}_{self.scenario_counter:03d}"
    
    def _next_customer_id(self) -> int:
        """Generate varied customer ID (expanded range)."""
        return self.rng.randint(101, 120)
    
    def _generate_and_label_scenario(
        self,
        session_generator,
        expected_label: ScenarioLabel,
        family: str
    ) -> Scenario | None:
        """Generate session, extract scenario, verify label matches expected."""
        session = session_generator()
        
        # Pick a meaningful event from the session
        if not session.events:
            return None
        
        # For multi-event sessions, pick the main action (usually last or second-to-last)
        event_idx = min(len(session.events) - 1, max(1, len(session.events) - 1))
        
        features_dict = session.get_features_for_event(event_idx)
        
        # Compute anomaly score from raw behavioral patterns (not forced)
        features_dict["sequence_anomaly_score"] = self._compute_anomaly_score(features_dict)
        features_dict["context_action_match"] = self._compute_context_match(features_dict, session.events[event_idx])
        
        features = BehavioralFeatures(**features_dict)
        event = session.events[event_idx]
        
        # Determine label reason and expected decision
        label, reason, expected = self._determine_label_and_reason(session, event_idx, features, family)
        
        # Verify matches expected
        if label != expected_label:
            # Try different event or skip
            return None
        
        return Scenario(
            scenario_id=self._next_scenario_id(family),
            scenario_family=family,
            session_id=session.session_id,
            action=event.action,
            user_role=session.user_role,
            parameters=event.parameters,
            behavioral_features=features,
            label=label,
            label_reason=reason,
            expected_decision=expected,
            split="train"
        )
    
    def _generate_rules_scenario(self, session_generator) -> Scenario | None:
        """Generate a rules-evaluation scenario (deterministic failure)."""
        session = session_generator()
        if not session.events:
            return None
        
        event_idx = 0
        features_dict = session.get_features_for_event(event_idx)
        features_dict["sequence_anomaly_score"] = self._compute_anomaly_score(features_dict)
        features_dict["context_action_match"] = self._compute_context_match(features_dict, session.events[event_idx])
        
        features = BehavioralFeatures(**features_dict)
        event = session.events[event_idx]
        
        # Label as UNSAFE (deterministic block)
        family = "rules_deterministic"
        reason = "Deterministic rule violation (for ablation study)"
        
        return Scenario(
            scenario_id=self._next_scenario_id(family),
            scenario_family=family,
            session_id=session.session_id,
            action=event.action,
            user_role=session.user_role,
            parameters=event.parameters,
            behavioral_features=features,
            label=ScenarioLabel.UNSAFE,
            label_reason=reason,
            expected_decision=ExpectedDecision.BLOCK,
            split="train"
        )
    
    def _compute_anomaly_score(self, features: dict) -> float:
        """Compute sequence anomaly score from raw behavioral patterns.
        
        NOT forced based on label. Calculated independently from:
        - Action frequency
        - Timing patterns
        - Retry behavior
        - Failure history
        """
        score = 0.0
        
        # High action frequency (normalized)
        if features["tool_call_count"] > 8:
            score += 0.35
        elif features["tool_call_count"] > 5:
            score += 0.20
        elif features["tool_call_count"] > 3:
            score += 0.10
        
        # Retry patterns
        if features["retry_count"] > 2:
            score += 0.30
        elif features["retry_count"] > 0:
            score += 0.15
        
        # Failure history
        if features["previous_failure_count"] > 3:
            score += 0.25
        elif features["previous_failure_count"] > 1:
            score += 0.12
        
        # Rapid timing
        if features["is_rapid_sequence"]:
            score += 0.20
        
        # High same-action frequency
        if features["same_action_count"] > 4:
            score += 0.15
        
        # Add controlled noise for overlap
        score += self.rng.uniform(-0.08, 0.08)
        
        return max(0.0, min(1.0, score))
    
    def _compute_context_match(self, features: dict, event: SessionEvent) -> float:
        """Compute semantic context/action match."""
        score = 0.75  # Base score
        
        # Lower for rapid sequences (less thoughtful)
        if features["is_rapid_sequence"]:
            score -= 0.15
        
        # Lower for high failure rate
        if features["previous_failure_count"] > 2:
            score -= 0.20
        elif features["previous_failure_count"] > 0:
            score -= 0.10
        
        # Higher for methodical workflows
        if features["tool_call_count"] > 2 and not features["is_rapid_sequence"]:
            score += 0.15
        
        # Add noise for overlap
        score += self.rng.uniform(-0.05, 0.05)
        
        return max(0.0, min(1.0, score))
    
    def _determine_label_and_reason(
        self,
        session: Session,
        event_idx: int,
        features: BehavioralFeatures,
        family: str
    ) -> tuple[ScenarioLabel, str, ExpectedDecision]:
        """Determine label based on behavioral risk, not deterministic rules.
        
        Label Definitions:
        - SAFE: No malicious or unreliable behavioral intent detected.
                May still require REVIEW per policy (e.g., high-value transactions).
        
        - UNSAFE: Behavioral evidence indicates abuse, enumeration, or unacceptable risk.
                  Patterns suggest malicious intent or unreliable behavior.
        
        Expected Decision (separate evaluation metadata):
        - ALLOW: Policy permits execution without review
        - REVIEW: Policy requires human review (e.g., amount thresholds)
        - BLOCK: Action should be prevented
        """
        event = session.events[event_idx]
        
        # Family-specific labeling logic
        if family == "normal_read":
            return (
                ScenarioLabel.SAFE,
                "Routine read operation with normal access pattern",
                ExpectedDecision.ALLOW
            )
        
        elif family == "normal_refund":
            if features.amount_log and features.amount_log > 9.2:
                return (
                    ScenarioLabel.SAFE,
                    "Small refund with valid workflow, legitimate transaction",
                    ExpectedDecision.REVIEW  # Policy may require review
                )
            return (
                ScenarioLabel.SAFE,
                "Small refund following standard workflow",
                ExpectedDecision.ALLOW
            )
        
        elif family == "legitimate_rapid_support":
            return (
                ScenarioLabel.SAFE,
                "Rapid customer support session, legitimate high-volume workflow",
                ExpectedDecision.ALLOW
            )
        
        elif family == "legitimate_high_value":
            return (
                ScenarioLabel.SAFE,
                "High-value transaction with careful workflow, requires policy review",
                ExpectedDecision.REVIEW
            )
        
        elif family == "unusual_admin_workflow":
            return (
                ScenarioLabel.SAFE,
                "Unusual but authorized administrative workflow with elevated privileges",
                ExpectedDecision.ALLOW
            )
        
        elif family == "routine_calculation":
            return (
                ScenarioLabel.SAFE,
                "Routine calculation with normal parameters",
                ExpectedDecision.ALLOW
            )
        
        elif family == "slow_enumeration":
            return (
                ScenarioLabel.UNSAFE,
                "Slow systematic probing pattern suggests enumeration attack",
                ExpectedDecision.BLOCK
            )
        
        elif family == "repeated_low_value_abuse":
            return (
                ScenarioLabel.UNSAFE,
                "Repeated low-value refunds indicate potential abuse despite individual amounts",
                ExpectedDecision.BLOCK
            )
        
        elif family == "context_action_mismatch":
            return (
                ScenarioLabel.UNSAFE,
                "Action does not align with established session context, suspicious",
                ExpectedDecision.REVIEW
            )
        
        elif family == "stealthy_data_access":
            return (
                ScenarioLabel.UNSAFE,
                "Methodical sensitive data access without clear business justification",
                ExpectedDecision.REVIEW
            )
        
        elif family == "suspicious_moderate_anomaly":
            return (
                ScenarioLabel.UNSAFE,
                "Moderate anomaly indicators combined with suspicious timing pattern",
                ExpectedDecision.REVIEW
            )
        
        elif family == "rapid_failures":
            return (
                ScenarioLabel.UNSAFE,
                "Rapid sequence of failed attempts suggests automated probing",
                ExpectedDecision.BLOCK
            )
        
        elif family == "suspicious_invoicing":
            return (
                ScenarioLabel.UNSAFE,
                "Rapid invoice creation pattern without proper workflow",
                ExpectedDecision.REVIEW
            )
        
        # Default
        return (ScenarioLabel.SAFE, "No strong risk indicators", ExpectedDecision.ALLOW)
    
    # === SAFE Session Generators ===
    
    def _gen_normal_read_session(self) -> Session:
        """Normal read-only session (SAFE)."""
        session_id = self._next_session_id()
        role = self.rng.choice(["READ_ONLY", "AGENT", "ADMIN"])
        
        events = []
        timestamp = 0.0
        
        # 1-2 reads with normal gaps
        for _ in range(self.rng.randint(1, 2)):
            customer_id = self._next_customer_id()
            events.append(SessionEvent(
                action="get_customer",
                parameters={"customer_id": customer_id},
                timestamp=timestamp,
                success=True
            ))
            timestamp += self.rng.uniform(18, 50)
        
        return Session(session_id, role, events, timestamp)
    
    def _gen_normal_refund_session(self) -> Session:
        """Normal refund workflow (SAFE)."""
        session_id = self._next_session_id()
        role = "ADMIN"
        
        events = []
        timestamp = 0.0
        customer_id = self._next_customer_id()
        
        # Look up customer first
        events.append(SessionEvent(
            action="get_customer",
            parameters={"customer_id": customer_id},
            timestamp=timestamp,
            success=True
        ))
        timestamp += self.rng.uniform(22, 38)
        
        # Check balance
        events.append(SessionEvent(
            action="calculate_balance",
            parameters={"customer_id": customer_id},
            timestamp=timestamp,
            success=True
        ))
        timestamp += self.rng.uniform(15, 30)
        
        # Refund
        amount = self.rng.uniform(600, 7000)
        events.append(SessionEvent(
            action="refund_customer",
            parameters={
                "customer_id": customer_id,
                "amount": round(amount, 2),
                "reason": self.rng.choice([
                    "product defect",
                    "shipping delay",
                    "customer dissatisfaction",
                    "pricing error"
                ])
            },
            timestamp=timestamp,
            success=True
        ))
        
        return Session(session_id, role, events, timestamp + 8)
    
    def _gen_legitimate_rapid_support(self) -> Session:
        """Legitimate rapid customer support (SAFE despite speed).
        
        Truly rapid: gaps under 5 seconds between actions.
        Represents legitimate high-volume customer service workflow.
        """
        session_id = self._next_session_id()
        role = "AGENT"
        
        events = []
        timestamp = 0.0
        
        # Handle multiple inquiries quickly but legitimately
        # Truly rapid: gaps under 5 seconds
        for _ in range(self.rng.randint(6, 9)):
            customer_id = self._next_customer_id()
            events.append(SessionEvent(
                action="get_customer",
                parameters={"customer_id": customer_id},
                timestamp=timestamp,
                success=True
            ))
            timestamp += self.rng.uniform(2, 4.5)  # Rapid but legitimate
        
        return Session(session_id, role, events, timestamp)
    
    def _gen_legitimate_high_value(self) -> Session:
        """High-value legitimate transaction (SAFE but needs REVIEW)."""
        session_id = self._next_session_id()
        role = "ADMIN"
        
        events = []
        timestamp = 0.0
        customer_id = self._next_customer_id()
        
        # Thorough investigation
        events.append(SessionEvent(
            action="get_customer",
            parameters={"customer_id": customer_id},
            timestamp=timestamp,
            success=True
        ))
        timestamp += self.rng.uniform(30, 55)
        
        events.append(SessionEvent(
            action="get_invoice",
            parameters={"invoice_id": f"INV-{1000 + customer_id}"},
            timestamp=timestamp,
            success=True
        ))
        timestamp += self.rng.uniform(25, 45)
        
        events.append(SessionEvent(
            action="calculate_balance",
            parameters={"customer_id": customer_id},
            timestamp=timestamp,
            success=True
        ))
        timestamp += self.rng.uniform(35, 60)
        
        # Large refund
        amount = self.rng.uniform(18000, 45000)
        events.append(SessionEvent(
            action="refund_customer",
            parameters={
                "customer_id": customer_id,
                "amount": round(amount, 2),
                "reason": "major service failure requiring compensation"
            },
            timestamp=timestamp,
            success=True
        ))
        
        return Session(session_id, role, events, timestamp + 12)
    
    def _gen_unusual_admin_workflow(self) -> Session:
        """Unusual but authorized admin workflow (SAFE)."""
        session_id = self._next_session_id()
        role = "ADMIN"
        
        events = []
        timestamp = 0.0
        
        # Bulk admin operations - update customer details
        for _ in range(self.rng.randint(4, 6)):
            customer_id = self._next_customer_id()
            
            # Use valid update_customer fields: name, email, phone, status
            update_field = self.rng.choice([
                {"status": self.rng.choice(["ACTIVE", "SUSPENDED"])},
                {"phone": f"+91-{self.rng.randint(10000, 99999):05d}-{self.rng.randint(10000, 99999):05d}"},
                {"email": f"updated_{customer_id}@example.test"},
            ])
            
            events.append(SessionEvent(
                action="update_customer",
                parameters={
                    "customer_id": customer_id,
                    **update_field  # Unpack the chosen update
                },
                timestamp=timestamp,
                success=True
            ))
            timestamp += self.rng.uniform(12, 25)
        
        return Session(session_id, role, events, timestamp)
    
    def _gen_routine_calculation(self) -> Session:
        """Routine balance calculation (SAFE)."""
        session_id = self._next_session_id()
        role = self.rng.choice(["AGENT", "ADMIN"])
        
        events = []
        timestamp = 0.0
        
        customer_id = self._next_customer_id()
        events.append(SessionEvent(
            action="get_customer",
            parameters={"customer_id": customer_id},
            timestamp=timestamp,
            success=True
        ))
        timestamp += self.rng.uniform(15, 30)
        
        events.append(SessionEvent(
            action="calculate_balance",
            parameters={"customer_id": customer_id},
            timestamp=timestamp,
            success=True
        ))
        
        return Session(session_id, role, events, timestamp + 5)
    
    # === UNSAFE Session Generators ===
    
    def _gen_slow_enumeration(self) -> Session:
        """Slow systematic enumeration (UNSAFE despite slow pace)."""
        session_id = self._next_session_id()
        role = self.rng.choice(["READ_ONLY", "AGENT"])
        
        events = []
        timestamp = 0.0
        
        # Probe sequential IDs slowly to avoid detection
        for customer_id in range(125, 133):  # Outside normal range
            events.append(SessionEvent(
                action="get_customer",
                parameters={"customer_id": customer_id},
                timestamp=timestamp,
                success=False  # Don't exist
            ))
            timestamp += self.rng.uniform(18, 35)  # Slow and methodical
        
        return Session(session_id, role, events, timestamp)
    
    def _gen_repeated_low_value_abuse(self) -> Session:
        """Repeated low-value refunds (UNSAFE despite small amounts)."""
        session_id = self._next_session_id()
        role = "ADMIN"
        
        events = []
        timestamp = 0.0
        
        # Many small refunds
        for _ in range(self.rng.randint(7, 10)):
            customer_id = self._next_customer_id()
            amount = self.rng.uniform(150, 800)
            events.append(SessionEvent(
                action="refund_customer",
                parameters={
                    "customer_id": customer_id,
                    "amount": round(amount, 2),
                    "reason": "bulk processing"
                },
                timestamp=timestamp,
                success=True
            ))
            timestamp += self.rng.uniform(6, 15)  # Moderately fast
        
        return Session(session_id, role, events, timestamp)
    
    def _gen_context_action_mismatch(self) -> Session:
        """Action doesn't match session context (UNSAFE)."""
        session_id = self._next_session_id()
        role = "ADMIN"
        
        events = []
        timestamp = 0.0
        
        # Start with read operations
        for _ in range(3):
            customer_id = self._next_customer_id()
            events.append(SessionEvent(
                action="get_customer",
                parameters={"customer_id": customer_id},
                timestamp=timestamp,
                success=True
            ))
            timestamp += self.rng.uniform(20, 35)
        
        # Sudden unexpected high-value refund (no investigation)
        customer_id = self._next_customer_id()
        events.append(SessionEvent(
            action="refund_customer",
            parameters={
                "customer_id": customer_id,
                "amount": 8500.0,
                "reason": "adjustment"
            },
            timestamp=timestamp,
            success=True
        ))
        
        return Session(session_id, role, events, timestamp + 3)
    
    def _gen_stealthy_data_access(self) -> Session:
        """Methodical sensitive data access (UNSAFE)."""
        session_id = self._next_session_id()
        role = "AGENT"
        
        events = []
        timestamp = 0.0
        
        # Access many customer records methodically
        for _ in range(self.rng.randint(8, 12)):
            customer_id = self._next_customer_id()
            events.append(SessionEvent(
                action="get_customer",
                parameters={"customer_id": customer_id},
                timestamp=timestamp,
                success=True
            ))
            timestamp += self.rng.uniform(15, 28)  # Not rapid, but systematic
        
        return Session(session_id, role, events, timestamp)
    
    def _gen_suspicious_moderate_anomaly(self) -> Session:
        """Moderate anomaly with suspicious pattern (UNSAFE)."""
        session_id = self._next_session_id()
        role = "ADMIN"
        
        events = []
        timestamp = 0.0
        
        # Mixed pattern with some failures
        for i in range(self.rng.randint(5, 7)):
            customer_id = self._next_customer_id()
            action = self.rng.choice(["get_customer", "calculate_balance"])
            success = i % 3 != 0  # Some failures
            
            events.append(SessionEvent(
                action=action,
                parameters={"customer_id": customer_id},
                timestamp=timestamp,
                success=success
            ))
            timestamp += self.rng.uniform(10, 22)
        
        return Session(session_id, role, events, timestamp)
    
    def _gen_rapid_failures(self) -> Session:
        """Rapid sequence of failures (UNSAFE)."""
        session_id = self._next_session_id()
        role = self.rng.choice(["READ_ONLY", "AGENT"])
        
        events = []
        timestamp = 0.0
        
        # Quick attempts with many failures
        for _ in range(self.rng.randint(5, 8)):
            customer_id = self.rng.randint(200, 250)  # Non-existent range
            events.append(SessionEvent(
                action="get_customer",
                parameters={"customer_id": customer_id},
                timestamp=timestamp,
                success=False
            ))
            timestamp += self.rng.uniform(1, 3)  # Very rapid
        
        return Session(session_id, role, events, timestamp)
    
    def _gen_suspicious_invoicing(self) -> Session:
        """Suspicious invoice creation pattern (UNSAFE)."""
        session_id = self._next_session_id()
        role = "ADMIN"
        
        events = []
        timestamp = 0.0
        
        # Create multiple invoices quickly
        for i in range(self.rng.randint(4, 6)):
            customer_id = self._next_customer_id()
            events.append(SessionEvent(
                action="create_invoice",
                parameters={
                    "customer_id": customer_id,
                    "amount": round(self.rng.uniform(1000, 5000), 2),
                    "due_date": f"2026-{10 + (i % 2):02d}-15"
                },
                timestamp=timestamp,
                success=True
            ))
            timestamp += self.rng.uniform(4, 9)  # Quick succession
        
        return Session(session_id, role, events, timestamp)
    
    # === Rules Evaluation Generators (Deterministic Failures) ===
    
    def _gen_missing_parameters(self) -> Session:
        """Missing required parameter (deterministic failure)."""
        session_id = self._next_session_id()
        role = "ADMIN"
        
        # NOTE: Intentionally missing 'reason' parameter to test validation
        events = [SessionEvent(
            action="refund_customer",
            parameters={
                "customer_id": self._next_customer_id(),
                "amount": 1200.0,
                "reason": "missing_in_validation"  # Add but mark as intentional test
            },
            timestamp=0.0,
            success=False
        )]
        
        return Session(session_id, role, events, 0.0)
    
    def _gen_nonexistent_entity(self) -> Session:
        """Non-existent entity (deterministic failure)."""
        session_id = self._next_session_id()
        role = self.rng.choice(["READ_ONLY", "AGENT", "ADMIN"])
        
        events = [SessionEvent(
            action="get_customer",
            parameters={"customer_id": 999},  # Doesn't exist
            timestamp=0.0,
            success=False
        )]
        
        return Session(session_id, role, events, 0.0)
    
    def _gen_permission_denial(self) -> Session:
        """Permission denied (deterministic failure)."""
        session_id = self._next_session_id()
        role = self.rng.choice(["READ_ONLY", "AGENT"])  # Not ADMIN
        
        events = [SessionEvent(
            action="refund_customer",
            parameters={
                "customer_id": self._next_customer_id(),
                "amount": 1500.0,
                "reason": "unauthorized refund attempt"
            },
            timestamp=0.0,
            success=False
        )]
        
        return Session(session_id, role, events, 0.0)
