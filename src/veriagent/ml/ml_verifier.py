"""
ML-Based Verification Component
================================

Uses trained Random Forest to detect behavioral anomalies.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Optional, Dict, Any

from veriagent.models import ProposedAction, Decision, VerificationResult
from veriagent.ml.feature_extractor import FeatureExtractor
from veriagent.ml.preprocessing import FeaturePreprocessor


class MLVerifier:
    """
    ML-based behavioral verifier using trained Random Forest.
    
    Complements rule-based verification with learned behavioral patterns.
    """
    
    def __init__(
        self,
        model_dir: Path | str = Path("experiments/outputs/phase5_models"),
        confidence_threshold: float = 0.5,
    ):
        """
        Initialize ML verifier.
        
        Args:
            model_dir: Directory containing trained model and preprocessor
            confidence_threshold: Probability threshold for UNSAFE classification
                                 (default 0.5 = balanced)
        """
        self.model_dir = Path(model_dir)
        self.confidence_threshold = confidence_threshold
        
        # Load components
        self.extractor = FeatureExtractor()
        self.preprocessor = FeaturePreprocessor.load(
            self.model_dir / 'preprocessor.json'
        )
        
        # Load Random Forest (best performing model)
        model_path = self.model_dir / 'random_forest.pkl'
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
    
    def verify(
        self,
        proposal: ProposedAction,
        behavioral_context: Dict[str, Any]
    ) -> VerificationResult:
        """
        Verify action using ML behavioral analysis.
        
        Args:
            proposal: The proposed action
            behavioral_context: Dict containing behavioral features:
                - tool_sensitivity: str ('LOW', 'MEDIUM', 'HIGH')
                - has_amount: bool
                - amount_log: float | None
                - num_parameters: int
                - tool_call_count: int
                - same_action_count: int
                - retry_count: int
                - previous_failure_count: int
                - seconds_since_last_action: float | None
                - is_rapid_sequence: bool
                - action_frequency: int
                - sequence_anomaly_score: float
                - context_action_match: float
        
        Returns:
            VerificationResult with ML decision and confidence scores
        """
        # Build feature dict
        scenario = {
            'action': proposal.action,
            'user_role': proposal.user_role,
            'behavioral_features': behavioral_context,
        }
        
        # Extract and preprocess
        try:
            features, _ = self.extractor.extract_features([scenario], return_labels=False)
            X = self.preprocessor.transform(features)
        except Exception as e:
            # If feature extraction fails, default to REVIEW with explanation
            return VerificationResult(
                decision=Decision.REVIEW,
                reasons=(f"ML feature extraction failed: {e}",),
                checks={'ml_extraction': False},
            )
        
        # Get prediction and probability
        prediction = self.model.predict(X)[0]  # 0=SAFE, 1=UNSAFE
        probabilities = self.model.predict_proba(X)[0]  # [P(SAFE), P(UNSAFE)]
        
        confidence = probabilities[1]  # Probability of UNSAFE
        
        # Determine decision
        if prediction == 1:  # Model says UNSAFE
            decision = Decision.BLOCK
            reason = f"ML behavioral anomaly detected (confidence: {confidence:.2%})"
        elif confidence >= 0.3:  # High uncertainty
            decision = Decision.REVIEW
            reason = f"ML uncertainty detected (UNSAFE probability: {confidence:.2%})"
        else:  # Model says SAFE with high confidence
            decision = Decision.ALLOW
            reason = f"ML behavioral check passed (SAFE probability: {probabilities[0]:.2%})"
        
        return VerificationResult(
            decision=decision,
            reasons=(reason,),
            checks={
                'ml_prediction': prediction == 0,  # True if SAFE
                'ml_confidence': float(confidence),
                'ml_safe_probability': float(probabilities[0]),
                'ml_unsafe_probability': float(probabilities[1]),
            },
        )


class HybridVerifier:
    """
    Hybrid verifier combining deterministic rules and ML behavioral analysis.
    
    Decision logic:
    1. Apply deterministic rules first (role permissions, policies)
    2. If rules BLOCK → BLOCK (hard constraint)
    3. If rules ALLOW → Check ML behavioral analysis
    4. If ML BLOCK → BLOCK (anomaly detected)
    5. If ML REVIEW → REVIEW (uncertainty)
    6. If ML ALLOW → ALLOW (both agree)
    7. If rules REVIEW → escalate to REVIEW regardless of ML
    """
    
    def __init__(
        self,
        rule_verifier,
        ml_verifier: MLVerifier,
        require_ml: bool = True,
    ):
        """
        Initialize hybrid verifier.
        
        Args:
            rule_verifier: RuleVerifier instance for deterministic checks
            ml_verifier: MLVerifier instance for behavioral analysis
            require_ml: If False, fall back to rules-only if ML fails
        """
        self.rule_verifier = rule_verifier
        self.ml_verifier = ml_verifier
        self.require_ml = require_ml
    
    def verify(
        self,
        proposal: ProposedAction,
        behavioral_context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """
        Verify action using both rules and ML.
        
        Args:
            proposal: The proposed action
            behavioral_context: Behavioral features for ML (if None, rules-only)
        
        Returns:
            Combined VerificationResult
        """
        # Step 1: Apply deterministic rules
        rule_result = self.rule_verifier.verify(proposal)
        
        # If rules block, respect that (hard constraint)
        if rule_result.decision == Decision.BLOCK:
            return VerificationResult(
                decision=Decision.BLOCK,
                reasons=rule_result.reasons + ("Rules blocked - ML not consulted",),
                checks={**rule_result.checks, 'ml_consulted': False},
            )
        
        # If no behavioral context, return rules-only result
        if behavioral_context is None:
            if self.require_ml:
                return VerificationResult(
                    decision=Decision.REVIEW,
                    reasons=rule_result.reasons + ("ML behavioral context missing",),
                    checks={**rule_result.checks, 'ml_consulted': False},
                )
            else:
                return rule_result
        
        # Step 2: Apply ML behavioral analysis
        try:
            ml_result = self.ml_verifier.verify(proposal, behavioral_context)
        except Exception as e:
            # ML failed
            if self.require_ml:
                return VerificationResult(
                    decision=Decision.REVIEW,
                    reasons=rule_result.reasons + (f"ML verification failed: {e}",),
                    checks={**rule_result.checks, 'ml_consulted': False, 'ml_error': True},
                )
            else:
                # Fall back to rules-only
                return rule_result
        
        # Step 3: Combine decisions
        combined_checks = {**rule_result.checks, **ml_result.checks, 'ml_consulted': True}
        combined_reasons = rule_result.reasons + ml_result.reasons
        
        # Decision priority: BLOCK > REVIEW > ALLOW
        if ml_result.decision == Decision.BLOCK:
            # ML detected anomaly → BLOCK
            final_decision = Decision.BLOCK
        elif rule_result.decision == Decision.REVIEW or ml_result.decision == Decision.REVIEW:
            # Either rules or ML want review → REVIEW
            final_decision = Decision.REVIEW
        else:
            # Both rules and ML say ALLOW → ALLOW
            final_decision = Decision.ALLOW
        
        return VerificationResult(
            decision=final_decision,
            reasons=combined_reasons,
            checks=combined_checks,
        )
