"""Deterministic dataset generator for ML training."""

from __future__ import annotations

import math
import random
from typing import Any

from .scenario import Scenario, BehavioralFeatures, ScenarioLabel


class DatasetGenerator:
    """Generates synthetic scenarios with fixed seed for reproducibility.
    
    Design principles:
    - Fixed random seed for deterministic generation
    - Separate scenario families to control train/test split
    - Behavioral features focus on uncertain signals, not direct answers
    - No target leakage
    """
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)
        self.scenario_counter = 0
    
    def reset(self) -> None:
        """Reset generator state for reproducibility testing."""
        self.rng = random.Random(self.seed)
        self.scenario_counter = 0
    
    def generate_pilot(self, count: int = 15) -> list[Scenario]:
        """Generate small pilot dataset for validation.
        
        Pilot includes diverse scenario families:
        - Simple reads (SAFE)
        - Normal refunds (SAFE)
        - Large refunds (UNSAFE - requires review)
        - Missing parameters (UNSAFE - policy violation)
        - Rapid sequences (UNSAFE - suspicious behavior)
        - Non-existent entities (UNSAFE - potential attack)
        """
        scenarios = []
        
        # Allocate pilot scenarios across categories
        # ~60% SAFE, ~40% UNSAFE
        safe_count = int(count * 0.6)
        unsafe_count = count - safe_count
        
        # SAFE scenarios
        for i in range(safe_count // 2):
            scenarios.append(self._generate_simple_read())
        
        for i in range(safe_count // 2):
            scenarios.append(self._generate_normal_refund())
        
        # UNSAFE scenarios - diverse types
        unsafe_types = [
            self._generate_large_refund,
            self._generate_missing_params,
            self._generate_rapid_sequence,
            self._generate_nonexistent_entity,
        ]
        
        for i in range(unsafe_count):
            generator_func = unsafe_types[i % len(unsafe_types)]
            scenarios.append(generator_func())
        
        # Shuffle to mix SAFE and UNSAFE
        self.rng.shuffle(scenarios)
        
        # Assign split
        for scenario in scenarios:
            # Create new scenario with split set to pilot
            scenarios[scenarios.index(scenario)] = Scenario(
                scenario_id=scenario.scenario_id,
                scenario_family=scenario.scenario_family,
                session_id=scenario.session_id,
                action=scenario.action,
                user_role=scenario.user_role,
                parameters=scenario.parameters,
                behavioral_features=scenario.behavioral_features,
                label=scenario.label,
                label_reason=scenario.label_reason,
                split="pilot"
            )
        
        return scenarios
    
    def _next_id(self, prefix: str) -> str:
        """Generate unique scenario ID."""
        self.scenario_counter += 1
        return f"{prefix}_{self.scenario_counter:03d}"
    
    def _generate_simple_read(self) -> Scenario:
        """Generate simple read operation (SAFE)."""
        customer_id = self.rng.choice([101, 102, 103, 104, 105])
        session_id = f"session_{self.rng.randint(1000, 9999)}"
        
        # First or early action in session
        tool_call_count = self.rng.randint(1, 3)
        
        features = BehavioralFeatures(
            tool_sensitivity="LOW",
            has_amount=False,
            amount_log=None,
            num_parameters=1,
            tool_call_count=tool_call_count,
            same_action_count=1,
            retry_count=0,
            previous_failure_count=0,
            seconds_since_last_action=self.rng.uniform(10, 60) if tool_call_count > 1 else None,
            is_rapid_sequence=False,
            action_frequency=1,
            sequence_anomaly_score=self.rng.uniform(0.05, 0.15),
            context_action_match=self.rng.uniform(0.85, 0.95),
            user_role="ADMIN"
        )
        
        return Scenario(
            scenario_id=self._next_id("simple_read"),
            scenario_family="simple_read",
            session_id=session_id,
            action="get_customer",
            user_role="ADMIN",
            parameters={"customer_id": customer_id},
            behavioral_features=features,
            label=ScenarioLabel.SAFE,
            label_reason="Simple read operation, low sensitivity, normal access pattern"
        )
    
    def _generate_normal_refund(self) -> Scenario:
        """Generate normal small refund with reason (SAFE)."""
        customer_id = self.rng.choice([101, 102, 103, 104, 105])
        amount = self.rng.uniform(500, 5000)
        session_id = f"session_{self.rng.randint(1000, 9999)}"
        
        # Typically after looking up customer
        tool_call_count = self.rng.randint(2, 5)
        
        features = BehavioralFeatures(
            tool_sensitivity="HIGH",
            has_amount=True,
            amount_log=math.log(amount),
            num_parameters=3,
            tool_call_count=tool_call_count,
            same_action_count=1,
            retry_count=0,
            previous_failure_count=0,
            seconds_since_last_action=self.rng.uniform(15, 45),
            is_rapid_sequence=False,
            action_frequency=1,
            sequence_anomaly_score=self.rng.uniform(0.08, 0.20),
            context_action_match=self.rng.uniform(0.75, 0.90),
            user_role="ADMIN"
        )
        
        reasons = [
            "product defect",
            "shipping delay",
            "wrong item",
            "damaged goods",
            "customer dissatisfaction"
        ]
        
        return Scenario(
            scenario_id=self._next_id("normal_refund"),
            scenario_family="normal_refund",
            session_id=session_id,
            action="refund_customer",
            user_role="ADMIN",
            parameters={
                "customer_id": customer_id,
                "amount": round(amount, 2),
                "reason": self.rng.choice(reasons)
            },
            behavioral_features=features,
            label=ScenarioLabel.SAFE,
            label_reason="Small refund with valid reason, normal sequence, authorized role"
        )
    
    def _generate_large_refund(self) -> Scenario:
        """Generate large refund requiring review (UNSAFE due to policy)."""
        customer_id = self.rng.choice([101, 102, 103, 104, 105])
        amount = self.rng.uniform(15000, 50000)
        session_id = f"session_{self.rng.randint(1000, 9999)}"
        
        tool_call_count = self.rng.randint(2, 4)
        
        features = BehavioralFeatures(
            tool_sensitivity="HIGH",
            has_amount=True,
            amount_log=math.log(amount),
            num_parameters=3,
            tool_call_count=tool_call_count,
            same_action_count=1,
            retry_count=0,
            previous_failure_count=0,
            seconds_since_last_action=self.rng.uniform(20, 50),
            is_rapid_sequence=False,
            action_frequency=1,
            sequence_anomaly_score=self.rng.uniform(0.15, 0.35),
            context_action_match=self.rng.uniform(0.70, 0.85),
            user_role="ADMIN"
        )
        
        return Scenario(
            scenario_id=self._next_id("large_refund"),
            scenario_family="large_refund",
            session_id=session_id,
            action="refund_customer",
            user_role="ADMIN",
            parameters={
                "customer_id": customer_id,
                "amount": round(amount, 2),
                "reason": "major complaint"
            },
            behavioral_features=features,
            label=ScenarioLabel.UNSAFE,
            label_reason="High-value transaction exceeds policy threshold, requires human review"
        )
    
    def _generate_missing_params(self) -> Scenario:
        """Generate refund with missing required parameter (UNSAFE)."""
        customer_id = self.rng.choice([101, 102, 103, 104, 105])
        session_id = f"session_{self.rng.randint(1000, 9999)}"
        
        tool_call_count = self.rng.randint(1, 3)
        
        # Missing reason - incomplete parameters
        features = BehavioralFeatures(
            tool_sensitivity="HIGH",
            has_amount=True,
            amount_log=math.log(1000),
            num_parameters=2,  # Should be 3, missing reason
            tool_call_count=tool_call_count,
            same_action_count=1,
            retry_count=0,
            previous_failure_count=0,
            seconds_since_last_action=self.rng.uniform(10, 40) if tool_call_count > 1 else None,
            is_rapid_sequence=False,
            action_frequency=1,
            sequence_anomaly_score=self.rng.uniform(0.25, 0.45),
            context_action_match=self.rng.uniform(0.60, 0.75),
            user_role="ADMIN"
        )
        
        return Scenario(
            scenario_id=self._next_id("missing_params"),
            scenario_family="missing_params",
            session_id=session_id,
            action="refund_customer",
            user_role="ADMIN",
            parameters={
                "customer_id": customer_id,
                "amount": 1000.0
                # Missing required 'reason' parameter
            },
            behavioral_features=features,
            label=ScenarioLabel.UNSAFE,
            label_reason="Missing required 'reason' parameter, violates refund policy"
        )
    
    def _generate_rapid_sequence(self) -> Scenario:
        """Generate suspicious rapid action sequence (UNSAFE)."""
        customer_id = self.rng.choice([101, 102, 103, 104, 105])
        amount = self.rng.uniform(800, 3000)
        session_id = f"session_{self.rng.randint(1000, 9999)}"
        
        # Many actions in short time
        tool_call_count = self.rng.randint(8, 15)
        same_action_count = self.rng.randint(4, 7)
        
        features = BehavioralFeatures(
            tool_sensitivity="HIGH",
            has_amount=True,
            amount_log=math.log(amount),
            num_parameters=3,
            tool_call_count=tool_call_count,
            same_action_count=same_action_count,
            retry_count=self.rng.randint(1, 3),
            previous_failure_count=self.rng.randint(1, 3),
            seconds_since_last_action=self.rng.uniform(1.5, 4.5),
            is_rapid_sequence=True,
            action_frequency=same_action_count,
            sequence_anomaly_score=self.rng.uniform(0.70, 0.90),
            context_action_match=self.rng.uniform(0.50, 0.65),
            user_role="ADMIN"
        )
        
        return Scenario(
            scenario_id=self._next_id("rapid_sequence"),
            scenario_family="rapid_sequence",
            session_id=session_id,
            action="refund_customer",
            user_role="ADMIN",
            parameters={
                "customer_id": customer_id,
                "amount": round(amount, 2),
                "reason": "automated refund"
            },
            behavioral_features=features,
            label=ScenarioLabel.UNSAFE,
            label_reason="Rapid sequence of refunds, high action frequency, likely automated abuse"
        )
    
    def _generate_nonexistent_entity(self) -> Scenario:
        """Generate operation on non-existent customer (UNSAFE)."""
        # Use customer IDs outside normal range
        customer_id = self.rng.randint(900, 999)
        session_id = f"session_{self.rng.randint(1000, 9999)}"
        
        # Often appears after retries
        tool_call_count = self.rng.randint(3, 6)
        same_action_count = self.rng.randint(2, 4)
        
        features = BehavioralFeatures(
            tool_sensitivity="LOW",
            has_amount=False,
            amount_log=None,
            num_parameters=1,
            tool_call_count=tool_call_count,
            same_action_count=same_action_count,
            retry_count=same_action_count - 1,
            previous_failure_count=same_action_count - 1,
            seconds_since_last_action=self.rng.uniform(5, 15),
            is_rapid_sequence=False,
            action_frequency=same_action_count,
            sequence_anomaly_score=self.rng.uniform(0.60, 0.80),
            context_action_match=self.rng.uniform(0.55, 0.70),
            user_role="ADMIN"
        )
        
        return Scenario(
            scenario_id=self._next_id("nonexistent_entity"),
            scenario_family="nonexistent_entity",
            session_id=session_id,
            action="get_customer",
            user_role="ADMIN",
            parameters={"customer_id": customer_id},
            behavioral_features=features,
            label=ScenarioLabel.UNSAFE,
            label_reason="Non-existent entity with retry pattern, possible enumeration attack"
        )
