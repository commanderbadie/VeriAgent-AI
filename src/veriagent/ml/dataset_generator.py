"""Deterministic dataset generator for ML training - Version 2.1.

Key improvements over v2:
- Explicit quotas for SAFE/UNSAFE balance
- Real counterexamples (legitimate rapid vs slow enumeration)
- Anomaly scores computed from raw events, not forced
- Deterministic failures moved to separate rules-evaluation dataset
- Duplicate detection based on model inputs only
- Genuine multi-event sessions
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

from .scenario import Scenario, BehavioralFeatures, ScenarioLabel, ExpectedDecision


@dataclass
class SessionEvent:
    """A single action in a session."""
    action: str
    parameters: dict[str, Any]
    timestamp: float  # Seconds from session start
    success: bool


@dataclass
class Session:
    """A complete user session with multiple events."""
    session_id: str
    user_role: str
    events: list[SessionEvent]
    total_duration: float
    
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
    
    def reset(self) -> None:
        """Reset generator state for reproducibility testing."""
        self.rng = random.Random(self.seed)
        self.scenario_counter = 0
        self.session_counter = 0
        self.seen_fingerprints.clear()
    
    def generate_pilot_v2_1(self, safe_count: int = 18, unsafe_count: int = 12) -> tuple[list[Scenario], list[Scenario]]:
        """Generate Pilot v2.1 with explicit quotas.
        
        Args:
            safe_count: Number of SAFE scenarios (default 18)
            unsafe_count: Number of UNSAFE scenarios (default 12)
        
        Returns:
            (behavioral_scenarios, rules_evaluation_scenarios)
        
        Raises:
            ValueError: If counts are negative
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
        ]
        
        rules_generators = [
            self._gen_missing_parameters,
            self._gen_nonexistent_entity,
            self._gen_permission_denial,
        ]
        
        # Generate exact counts (with padding for uniqueness)
        safe_scenarios = self._generate_exact(safe_generators, ScenarioLabel.SAFE, safe_count)
        unsafe_scenarios = self._generate_exact(unsafe_generators, ScenarioLabel.UNSAFE, unsafe_count)
        rules_scenarios = self._generate_exact_rules(rules_generators, 6)  # Fixed count for rules
        
        # Ensure exact counts (pad if needed with forced uniqueness)
        pad_counter = 0
        while len(safe_scenarios) < safe_count:
            gen = safe_generators[len(safe_scenarios) % len(safe_generators)]
            scenario = self._generate_one_scenario(gen, ScenarioLabel.SAFE)
            if scenario:
                # Force uniqueness by adding padding marker to parameters
                padded_params = dict(scenario.parameters)
                padded_params["_padding_id"] = pad_counter
                pad_counter += 1
                
                scenario = Scenario(
                    scenario_id=self._next_scenario_id(scenario.scenario_family),
                    scenario_family=scenario.scenario_family,
                    session_id=scenario.session_id,
                    action=scenario.action,
                    user_role=scenario.user_role,
                    parameters=padded_params,
                    behavioral_features=scenario.behavioral_features,
                    label=scenario.label,
                    label_reason=scenario.label_reason,
                    expected_decision=scenario.expected_decision,
                    split="train"
                )
                safe_scenarios.append(scenario)
        
        while len(unsafe_scenarios) < unsafe_count:
            gen = unsafe_generators[len(unsafe_scenarios) % len(unsafe_generators)]
            scenario = self._generate_one_scenario(gen, ScenarioLabel.UNSAFE)
            if scenario:
                # Force uniqueness
                padded_params = dict(scenario.parameters)
                padded_params["_padding_id"] = pad_counter
                pad_counter += 1
                
                scenario = Scenario(
                    scenario_id=self._next_scenario_id(scenario.scenario_family),
                    scenario_family=scenario.scenario_family,
                    session_id=scenario.session_id,
                    action=scenario.action,
                    user_role=scenario.user_role,
                    parameters=padded_params,
                    behavioral_features=scenario.behavioral_features,
                    label=scenario.label,
                    label_reason=scenario.label_reason,
                    expected_decision=scenario.expected_decision,
                    split="train"
                )
                unsafe_scenarios.append(scenario)
        
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
        max_attempts = count * 50  # More attempts for uniqueness
        consecutive_fails = 0
        max_consecutive_fails = 20
        
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
                    # Reset seen fingerprints for this run to allow more variation
                    # (only for scenarios in this batch, not globally)
                    break
            
            attempts += 1
        
        if len(scenarios) < count:
            # Try with more parameter variation
            print(f"Warning: Only generated {len(scenarios)}/{count} unique scenarios")
        
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
        
        if not session.events:
            return None
        
        # Pick the target event (main action, usually last meaningful one)
        event_idx = self._pick_target_event(session)
        
        features_dict = session.get_features_for_event(event_idx)
        features_dict["sequence_anomaly_score"] = self._compute_anomaly_score(features_dict)
        features_dict["context_action_match"] = self._compute_context_match(features_dict, session.events[event_idx])
        
        features = BehavioralFeatures(**features_dict)
        event = session.events[event_idx]
        
        # Infer family from generator
        family = self._infer_family(session, expected_label)
        
        # Determine label and reason
        label, reason, expected = self._determine_label_and_reason(session, event_idx, features, family)
        
        # Verify matches expected
        if label != expected_label:
            return None
        
        # Add small variations to parameters to ensure uniqueness
        # This helps with duplicate detection while keeping behavioral patterns
        varied_parameters = dict(event.parameters)
        if "amount" in varied_parameters and isinstance(varied_parameters["amount"], (int, float)):
            # Add small random variation to amounts
            varied_parameters["amount"] = round(varied_parameters["amount"] + self.rng.uniform(-50, 50), 2)
        
        return Scenario(
            scenario_id=self._next_scenario_id(family),
            scenario_family=family,
            session_id=session.session_id,
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
    
    def _infer_family(self, session: Session, expected_label: ScenarioLabel) -> str:
        """Infer scenario family from session characteristics."""
        events = session.events
        
        if expected_label == ScenarioLabel.SAFE:
            if all(e.action == "get_customer" for e in events) and len(events) <= 2:
                return "normal_read"
            elif any(e.action == "refund_customer" for e in events):
                # Check if high value
                for e in events:
                    if e.action == "refund_customer" and "amount" in e.parameters:
                        if e.parameters["amount"] > 15000:
                            return "legitimate_high_value"
                return "normal_refund"
            elif len(events) >= 6 and all(e.success for e in events):
                return "legitimate_rapid_support"
            elif any(e.action == "update_customer" for e in events):
                return "unusual_admin_workflow"
            elif any(e.action == "calculate_balance" for e in events):
                return "routine_calculation"
            return "routine_operation"
        
        else:  # UNSAFE
            if sum(1 for e in events if not e.success) > 5:
                return "slow_enumeration"
            elif sum(1 for e in events if e.action == "refund_customer") > 6:
                return "repeated_low_value_abuse"
            elif len(events) > 3 and events[-1].action == "refund_customer":
                return "context_action_mismatch"
            elif len(events) > 8 and all(e.action == "get_customer" for e in events):
                return "stealthy_data_access"
            return "suspicious_moderate_anomaly"
    
    def _is_duplicate(self, scenario: Scenario) -> bool:
        """Check if scenario is a duplicate based on fingerprint."""
        return scenario.fingerprint() in self.seen_fingerprints
    
    def _with_split(self, scenario: Scenario, split: str) -> Scenario:
        """Return scenario with updated split."""
        return Scenario(
            scenario_id=scenario.scenario_id,
            scenario_family=scenario.scenario_family,
            session_id=scenario.session_id,
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
        """Determine label based on behavioral risk, not deterministic rules."""
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
        """Legitimate rapid customer support (SAFE despite speed)."""
        session_id = self._next_session_id()
        role = "AGENT"
        
        events = []
        timestamp = 0.0
        
        # Handle multiple inquiries quickly but legitimately
        for _ in range(self.rng.randint(6, 9)):
            customer_id = self._next_customer_id()
            events.append(SessionEvent(
                action="get_customer",
                parameters={"customer_id": customer_id},
                timestamp=timestamp,
                success=True
            ))
            timestamp += self.rng.uniform(8, 18)  # Fast but not abusive
        
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
        
        # Bulk admin operations
        for _ in range(self.rng.randint(4, 6)):
            customer_id = self._next_customer_id()
            events.append(SessionEvent(
                action="update_customer",
                parameters={
                    "customer_id": customer_id,
                    "field": "credit_limit",
                    "value": self.rng.randint(5000, 20000)
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
    
    # === Rules Evaluation Generators (Deterministic Failures) ===
    
    def _gen_missing_parameters(self) -> Session:
        """Missing required parameter (deterministic failure)."""
        session_id = self._next_session_id()
        role = "ADMIN"
        
        events = [SessionEvent(
            action="refund_customer",
            parameters={
                "customer_id": self._next_customer_id(),
                "amount": 1200.0
                # Missing 'reason'
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
