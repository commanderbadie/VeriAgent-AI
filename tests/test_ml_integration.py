"""
Tests for ML Integration with VeriAgent
=======================================

Tests the complete pipeline:
- ML verifier using trained Random Forest
- Hybrid verifier combining rules + ML
- End-to-end verification
"""

import unittest
from pathlib import Path

from veriagent.models import ProposedAction, Decision
from veriagent.verifier import RuleVerifier
from veriagent.ml.ml_verifier import MLVerifier, HybridVerifier


class TestMLVerifier(unittest.TestCase):
    """Test ML-based verification."""
    
    @classmethod
    def setUpClass(cls):
        """Load ML verifier once for all tests."""
        model_dir = Path('experiments/outputs/phase5_models')
        if not (model_dir / 'random_forest.pkl').exists():
            raise unittest.SkipTest("Trained model not found - run training first")
        
        cls.ml_verifier = MLVerifier(model_dir=model_dir)
    
    def test_ml_verifier_loads(self):
        """Test ML verifier initializes correctly."""
        self.assertIsNotNone(self.ml_verifier.model)
        self.assertIsNotNone(self.ml_verifier.preprocessor)
        self.assertIsNotNone(self.ml_verifier.extractor)
    
    def test_safe_action_allowed(self):
        """Test ML allows normal safe action."""
        proposal = ProposedAction(
            action='calculate_balance',  # No entity reference needed
            user_role='AGENT',
            parameters={'account_id': 123}
        )
        
        behavioral_context = {
            'tool_sensitivity': 'LOW',
            'has_amount': False,
            'amount_log': None,
            'num_parameters': 1,
            'tool_call_count': 3,
            'same_action_count': 2,
            'retry_count': 0,
            'previous_failure_count': 0,
            'seconds_since_last_action': 5.0,
            'is_rapid_sequence': False,
            'action_frequency': 2,
            'sequence_anomaly_score': 0.05,
            'context_action_match': 0.95,
        }
        
        result = self.ml_verifier.verify(proposal, behavioral_context)
        
        # ML should allow normal behavior
        self.assertEqual(result.decision, Decision.ALLOW)
        self.assertIn('ml_safe_probability', result.checks)
        self.assertGreater(result.checks['ml_safe_probability'], 0.5)
    
    def test_unsafe_action_blocked(self):
        """Test ML blocks suspicious action."""
        proposal = ProposedAction(
            action='refund_customer',
            user_role='AGENT',
            parameters={'customer_id': 123, 'amount': 50000}
        )
        
        # Highly suspicious behavioral pattern
        behavioral_context = {
            'tool_sensitivity': 'HIGH',
            'has_amount': True,
            'amount_log': 10.8,  # Very large
            'num_parameters': 2,
            'tool_call_count': 15,  # Many calls
            'same_action_count': 8,  # Repeated attempts
            'retry_count': 5,  # Multiple retries
            'previous_failure_count': 3,
            'seconds_since_last_action': 0.1,  # Rapid
            'is_rapid_sequence': True,
            'action_frequency': 8,
            'sequence_anomaly_score': 0.95,  # Very anomalous
            'context_action_match': 0.1,  # Doesn't match context
        }
        
        result = self.ml_verifier.verify(proposal, behavioral_context)
        
        # ML should block or review suspicious behavior
        self.assertIn(result.decision, [Decision.BLOCK, Decision.REVIEW])
        self.assertIn('ml_unsafe_probability', result.checks)


class TestHybridVerifier(unittest.TestCase):
    """Test hybrid rules + ML verification."""
    
    @classmethod
    def setUpClass(cls):
        """Set up hybrid verifier."""
        model_dir = Path('experiments/outputs/phase5_models')
        if not (model_dir / 'random_forest.pkl').exists():
            raise unittest.SkipTest("Trained model not found - run training first")
        
        cls.rule_verifier = RuleVerifier()
        cls.ml_verifier = MLVerifier(model_dir=model_dir)
        cls.hybrid_verifier = HybridVerifier(
            rule_verifier=cls.rule_verifier,
            ml_verifier=cls.ml_verifier,
        )
    
    def test_rules_block_overrides_ml(self):
        """Test that rule-based BLOCK always wins."""
        # Action not permitted for READ_ONLY role
        proposal = ProposedAction(
            action='refund_customer',
            user_role='READ_ONLY',
            parameters={'customer_id': 123, 'amount': 100}
        )
        
        # Even with safe behavioral pattern
        behavioral_context = {
            'tool_sensitivity': 'LOW',
            'has_amount': False,
            'amount_log': None,
            'num_parameters': 1,
            'tool_call_count': 1,
            'same_action_count': 1,
            'retry_count': 0,
            'previous_failure_count': 0,
            'seconds_since_last_action': 10.0,
            'is_rapid_sequence': False,
            'action_frequency': 1,
            'sequence_anomaly_score': 0.0,
            'context_action_match': 1.0,
        }
        
        result = self.hybrid_verifier.verify(proposal, behavioral_context)
        
        # Rules should block regardless of ML
        self.assertEqual(result.decision, Decision.BLOCK)
        self.assertFalse(result.checks['ml_consulted'])
    
    def test_both_allow_succeeds(self):
        """Test that action allowed when both rules and ML agree."""
        proposal = ProposedAction(
            action='calculate_balance',  # No entity reference needed
            user_role='AGENT',
            parameters={'account_id': 123}
        )
        
        behavioral_context = {
            'tool_sensitivity': 'LOW',
            'has_amount': False,
            'amount_log': None,
            'num_parameters': 1,
            'tool_call_count': 2,
            'same_action_count': 1,
            'retry_count': 0,
            'previous_failure_count': 0,
            'seconds_since_last_action': 8.0,
            'is_rapid_sequence': False,
            'action_frequency': 1,
            'sequence_anomaly_score': 0.03,
            'context_action_match': 0.98,
        }
        
        result = self.hybrid_verifier.verify(proposal, behavioral_context)
        
        # Both should allow
        self.assertEqual(result.decision, Decision.ALLOW)
        self.assertTrue(result.checks['ml_consulted'])
        self.assertTrue(result.checks['permission'])
    
    def test_ml_blocks_overrides_rules_allow(self):
        """Test that ML can block even when rules allow."""
        proposal = ProposedAction(
            action='calculate_balance',  # Action allowed for ADMIN, no entity check
            user_role='ADMIN',
            parameters={'account_id': 123}
        )
        
        # Rules allow (ADMIN can update_customer)
        # But behavioral pattern is suspicious
        behavioral_context = {
            'tool_sensitivity': 'MEDIUM',
            'has_amount': False,
            'amount_log': None,
            'num_parameters': 2,
            'tool_call_count': 20,  # Unusual volume
            'same_action_count': 15,  # Repeated updates
            'retry_count': 8,
            'previous_failure_count': 5,
            'seconds_since_last_action': 0.05,  # Very rapid
            'is_rapid_sequence': True,
            'action_frequency': 15,
            'sequence_anomaly_score': 0.98,  # Highly anomalous
            'context_action_match': 0.05,  # Wrong context
        }
        
        result = self.hybrid_verifier.verify(proposal, behavioral_context)
        
        # ML should escalate to at least REVIEW
        self.assertIn(result.decision, [Decision.BLOCK, Decision.REVIEW])
        self.assertTrue(result.checks['ml_consulted'])
    
    def test_missing_behavioral_context_requires_review(self):
        """Test that missing ML context triggers review when required."""
        proposal = ProposedAction(
            action='calculate_balance',  # No entity reference needed
            user_role='AGENT',
            parameters={'account_id': 123}
        )
        
        # No behavioral context provided
        result = self.hybrid_verifier.verify(proposal, behavioral_context=None)
        
        # Should require review when ML is required but context missing
        self.assertEqual(result.decision, Decision.REVIEW)
        self.assertFalse(result.checks.get('ml_consulted', False))


class TestEndToEnd(unittest.TestCase):
    """End-to-end integration tests."""
    
    @classmethod
    def setUpClass(cls):
        """Set up complete system."""
        model_dir = Path('experiments/outputs/phase5_models')
        if not (model_dir / 'random_forest.pkl').exists():
            raise unittest.SkipTest("Trained model not found")
        
        cls.hybrid_verifier = HybridVerifier(
            rule_verifier=RuleVerifier(),
            ml_verifier=MLVerifier(model_dir=model_dir),
        )
    
    def test_normal_workflow_allowed(self):
        """Test typical safe workflow is allowed."""
        proposal = ProposedAction(
            action='calculate_balance',  # No entity reference needed
            user_role='AGENT',
            parameters={'account_id': 100}
        )
        
        behavioral_context = {
            'tool_sensitivity': 'LOW',
            'has_amount': False,
            'amount_log': None,
            'num_parameters': 1,
            'tool_call_count': 3,
            'same_action_count': 2,
            'retry_count': 0,
            'previous_failure_count': 0,
            'seconds_since_last_action': 6.5,
            'is_rapid_sequence': False,
            'action_frequency': 2,
            'sequence_anomaly_score': 0.08,
            'context_action_match': 0.92,
        }
        
        result = self.hybrid_verifier.verify(proposal, behavioral_context)
        
        self.assertEqual(result.decision, Decision.ALLOW)
        self.assertTrue(result.checks['permission'])
        self.assertTrue(result.checks['ml_consulted'])
    
    def test_attack_scenario_blocked(self):
        """Test that attack scenario is detected and blocked."""
        # Simulated credential stuffing attack
        proposal = ProposedAction(
            action='calculate_balance',  # Rapid enumeration
            user_role='AGENT',
            parameters={'account_id': 999}
        )
        
        behavioral_context = {
            'tool_sensitivity': 'LOW',
            'has_amount': False,
            'amount_log': None,
            'num_parameters': 1,
            'tool_call_count': 50,  # Rapid enumeration
            'same_action_count': 50,
            'retry_count': 0,
            'previous_failure_count': 0,
            'seconds_since_last_action': 0.01,  # Automated
            'is_rapid_sequence': True,
            'action_frequency': 50,
            'sequence_anomaly_score': 0.99,
            'context_action_match': 0.02,
        }
        
        result = self.hybrid_verifier.verify(proposal, behavioral_context)
        
        # System should block or escalate
        self.assertIn(result.decision, [Decision.BLOCK, Decision.REVIEW])


if __name__ == '__main__':
    unittest.main()
