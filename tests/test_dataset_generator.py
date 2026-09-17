"""Tests for ML dataset generator."""

import unittest
from pathlib import Path
import tempfile
import shutil

from veriagent.ml import (
    DatasetGenerator,
    DatasetValidator,
    Scenario,
    ScenarioLabel,
)
from veriagent.ml.dataset_validator import (
    load_scenarios_from_jsonl,
    save_scenarios_to_jsonl,
)


class TestDatasetGenerator(unittest.TestCase):
    """Test dataset generation with determinism and validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.generator = DatasetGenerator(seed=42)
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        """Clean up temporary files."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_deterministic_generation(self):
        """Verify same seed produces identical output."""
        gen1 = DatasetGenerator(seed=42)
        gen2 = DatasetGenerator(seed=42)
        
        scenarios1, _ = gen1.generate_pilot_v2_1(safe_count=6, unsafe_count=4)
        scenarios2, _ = gen2.generate_pilot_v2_1(safe_count=6, unsafe_count=4)
        
        self.assertEqual(len(scenarios1), len(scenarios2))
        self.assertEqual(len(scenarios1), 10, "Should generate exactly requested count")
        
        for s1, s2 in zip(scenarios1, scenarios2):
            self.assertEqual(s1.scenario_id, s2.scenario_id)
            self.assertEqual(s1.label, s2.label)
            self.assertEqual(s1.parameters, s2.parameters)
            self.assertEqual(
                s1.behavioral_features.tool_call_count,
                s2.behavioral_features.tool_call_count
            )
    
    def test_unique_scenario_ids(self):
        """Verify all scenario IDs are unique."""
        scenarios, _ = self.generator.generate_pilot_v2_1(safe_count=12, unsafe_count=8)
        ids = [s.scenario_id for s in scenarios]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate scenario IDs found")
        self.assertEqual(len(ids), 20, "Should generate exactly requested count")
    
    def test_explicit_quotas(self):
        """Verify explicit quotas are met exactly."""
        scenarios, _ = self.generator.generate_pilot_v2_1(safe_count=12, unsafe_count=8)
        
        safe_count = sum(1 for s in scenarios if s.label == ScenarioLabel.SAFE)
        unsafe_count = sum(1 for s in scenarios if s.label == ScenarioLabel.UNSAFE)
        
        self.assertEqual(safe_count, 12, "Should have exactly 12 SAFE scenarios")
        self.assertEqual(unsafe_count, 8, "Should have exactly 8 UNSAFE scenarios")
    
    def test_no_leakage_features(self):
        """Verify no prohibited leakage features in parameters."""
        scenarios, _ = self.generator.generate_pilot_v2_1(safe_count=10, unsafe_count=5)
        
        prohibited = {
            "permission_denied", "policy_violated", "expected_decision",
            "is_unsafe", "should_block", "rule_result", "final_decision",
            "verifier_decision"
        }
        
        for scenario in scenarios:
            for key in scenario.parameters.keys():
                self.assertNotIn(
                    key, prohibited,
                    f"Scenario {scenario.scenario_id} contains leakage feature: {key}"
                )
    
    def test_scenario_validation(self):
        """Verify all generated scenarios pass validation."""
        scenarios, _ = self.generator.generate_pilot_v2_1(safe_count=10, unsafe_count=5)
        
        for scenario in scenarios:
            errors = scenario.validate()
            self.assertEqual(
                len(errors), 0,
                f"Scenario {scenario.scenario_id} validation failed: {errors}"
            )
    
    def test_label_justification(self):
        """Verify all scenarios have label reasons."""
        scenarios, _ = self.generator.generate_pilot_v2_1(safe_count=10, unsafe_count=5)
        
        for scenario in scenarios:
            self.assertTrue(
                scenario.label_reason,
                f"Scenario {scenario.scenario_id} missing label_reason"
            )
            self.assertGreater(
                len(scenario.label_reason), 10,
                f"Scenario {scenario.scenario_id} has too short label_reason"
            )
    
    def test_feature_value_ranges(self):
        """Verify feature values are within valid ranges."""
        scenarios, _ = self.generator.generate_pilot_v2_1(safe_count=10, unsafe_count=5)
        
        for scenario in scenarios:
            features = scenario.behavioral_features
            
            # Non-negative counts
            self.assertGreaterEqual(features.tool_call_count, 0)
            self.assertGreaterEqual(features.same_action_count, 0)
            self.assertGreaterEqual(features.retry_count, 0)
            self.assertGreaterEqual(features.previous_failure_count, 0)
            self.assertGreaterEqual(features.num_parameters, 0)
            
            # Bounded scores
            self.assertGreaterEqual(features.sequence_anomaly_score, 0)
            self.assertLessEqual(features.sequence_anomaly_score, 1)
            self.assertGreaterEqual(features.context_action_match, 0)
            self.assertLessEqual(features.context_action_match, 1)
            
            # Logical constraints
            self.assertLessEqual(
                features.same_action_count,
                features.tool_call_count,
                f"Scenario {scenario.scenario_id}: same_action_count > tool_call_count"
            )
    
    def test_scenario_families(self):
        """Verify scenarios have meaningful family groupings."""
        scenarios, _ = self.generator.generate_pilot_v2_1(safe_count=12, unsafe_count=8)
        
        families = set(s.scenario_family for s in scenarios)
        
        # Should have multiple distinct families (at least 8 for counterexamples)
        self.assertGreaterEqual(
            len(families), 8,
            f"Only {len(families)} families, need at least 8 for counterexamples"
        )
        
        # Each scenario should have a family
        for scenario in scenarios:
            self.assertTrue(
                scenario.scenario_family,
                f"Scenario {scenario.scenario_id} missing scenario_family"
            )
    
    def test_user_role_consistency(self):
        """Verify user_role matches between scenario and features."""
        scenarios, _ = self.generator.generate_pilot_v2_1(safe_count=10, unsafe_count=5)
        
        for scenario in scenarios:
            self.assertEqual(
                scenario.user_role,
                scenario.behavioral_features.user_role,
                f"Scenario {scenario.scenario_id}: role mismatch"
            )
    
    def test_correct_role_vocabulary(self):
        """Verify roles match VeriAgent vocabulary."""
        scenarios, _ = self.generator.generate_pilot_v2_1(safe_count=12, unsafe_count=8)
        
        valid_roles = {"ADMIN", "AGENT", "READ_ONLY"}
        for scenario in scenarios:
            self.assertIn(
                scenario.user_role,
                valid_roles,
                f"Scenario {scenario.scenario_id} has invalid role: {scenario.user_role}"
            )
    
    def test_rules_evaluation_separation(self):
        """Verify deterministic failures are separated."""
        _, rules_scenarios = self.generator.generate_pilot_v2_1(safe_count=12, unsafe_count=8)
        
        self.assertGreater(len(rules_scenarios), 0, "Should have rules evaluation scenarios")
        
        # All should be in rules_eval split
        for scenario in rules_scenarios:
            self.assertEqual(scenario.split, "rules_eval")
            self.assertEqual(scenario.label, ScenarioLabel.UNSAFE)
    
    def test_no_duplicates_generated(self):
        """Verify no duplicate fingerprints in generated dataset."""
        scenarios, _ = self.generator.generate_pilot_v2_1(safe_count=12, unsafe_count=8)
        
        fingerprints = [s.fingerprint() for s in scenarios]
        unique_fingerprints = set(fingerprints)
        
        self.assertEqual(
            len(fingerprints),
            len(unique_fingerprints),
            f"Found {len(fingerprints) - len(unique_fingerprints)} duplicate scenarios"
        )
    
    def test_requested_count_is_exact(self):
        """Verify total count matches request exactly."""
        for safe, unsafe in [(10, 5), (6, 4), (18, 12), (20, 10)]:
            with self.subTest(safe=safe, unsafe=unsafe):
                gen = DatasetGenerator(seed=42 + safe + unsafe)
                scenarios, _ = gen.generate_pilot_v2_1(safe_count=safe, unsafe_count=unsafe)
                self.assertEqual(len(scenarios), safe + unsafe,
                                f"Expected {safe + unsafe}, got {len(scenarios)}")
    
    def test_safe_quota_is_exact(self):
        """Verify SAFE count matches request exactly."""
        scenarios, _ = self.generator.generate_pilot_v2_1(safe_count=15, unsafe_count=10)
        safe_count = sum(1 for s in scenarios if s.label == ScenarioLabel.SAFE)
        self.assertEqual(safe_count, 15, f"Expected 15 SAFE, got {safe_count}")
    
    def test_unsafe_quota_is_exact(self):
        """Verify UNSAFE count matches request exactly."""
        scenarios, _ = self.generator.generate_pilot_v2_1(safe_count=12, unsafe_count=18)
        unsafe_count = sum(1 for s in scenarios if s.label == ScenarioLabel.UNSAFE)
        self.assertEqual(unsafe_count, 18, f"Expected 18 UNSAFE, got {unsafe_count}")
    
    def test_zero_counts(self):
        """Verify generator handles zero counts."""
        scenarios_a, _ = self.generator.generate_pilot_v2_1(safe_count=0, unsafe_count=5)
        self.assertEqual(len(scenarios_a), 5)
        self.assertTrue(all(s.label == ScenarioLabel.UNSAFE for s in scenarios_a))
        
        gen2 = DatasetGenerator(seed=43)
        scenarios_b, _ = gen2.generate_pilot_v2_1(safe_count=5, unsafe_count=0)
        self.assertEqual(len(scenarios_b), 5)
        self.assertTrue(all(s.label == ScenarioLabel.SAFE for s in scenarios_b))
    
    def test_small_counts(self):
        """Verify generator handles small counts."""
        scenarios, _ = self.generator.generate_pilot_v2_1(safe_count=1, unsafe_count=1)
        self.assertEqual(len(scenarios), 2)
        labels = [s.label for s in scenarios]
        self.assertIn(ScenarioLabel.SAFE, labels)
        self.assertIn(ScenarioLabel.UNSAFE, labels)
    
    def test_negative_count_rejected(self):
        """Verify negative counts raise ValueError."""
        with self.assertRaises(ValueError):
            self.generator.generate_pilot_v2_1(safe_count=-1, unsafe_count=5)
        
        with self.assertRaises(ValueError):
            self.generator.generate_pilot_v2_1(safe_count=5, unsafe_count=-1)
    
    def test_same_seed_is_identical(self):
        """Verify same seed produces identical scenarios."""
        gen1 = DatasetGenerator(seed=100)
        scenarios1, _ = gen1.generate_pilot_v2_1(safe_count=8, unsafe_count=6)
        
        gen2 = DatasetGenerator(seed=100)
        scenarios2, _ = gen2.generate_pilot_v2_1(safe_count=8, unsafe_count=6)
        
        self.assertEqual(len(scenarios1), len(scenarios2))
        for s1, s2 in zip(scenarios1, scenarios2):
            self.assertEqual(s1.scenario_id, s2.scenario_id)
            self.assertEqual(s1.label, s2.label)
            self.assertEqual(s1.action, s2.action)
            self.assertEqual(s1.parameters, s2.parameters)
    
    def test_no_duplicate_model_inputs(self):
        """Verify no duplicate model inputs (fingerprints)."""
        scenarios, _ = self.generator.generate_pilot_v2_1(safe_count=18, unsafe_count=12)
        
        fingerprints = [s.fingerprint() for s in scenarios]
        self.assertEqual(len(fingerprints), len(set(fingerprints)),
                        "Duplicate model inputs detected")


class TestDatasetValidator(unittest.TestCase):
    """Test dataset validation logic."""
    
    def test_valid_dataset_passes(self):
        """Verify validator accepts valid dataset."""
        generator = DatasetGenerator(seed=42)
        scenarios, _ = generator.generate_pilot_v2_1(safe_count=6, unsafe_count=4)
        
        validator = DatasetValidator(scenarios)
        is_valid = validator.validate()
        
        self.assertTrue(is_valid, f"Validation failed:\n{validator.report()}")
    
    def test_duplicate_ids_detected(self):
        """Verify validator detects duplicate IDs."""
        generator = DatasetGenerator(seed=42)
        scenarios, _ = generator.generate_pilot_v2_1(safe_count=3, unsafe_count=2)
        
        # Introduce duplicate
        scenarios.append(scenarios[0])
        
        validator = DatasetValidator(scenarios)
        is_valid = validator.validate()
        
        self.assertFalse(is_valid)
        self.assertTrue(any("Duplicate scenario IDs" in err for err in validator.errors))
    
    def test_validation_report_generation(self):
        """Verify validation report is generated."""
        generator = DatasetGenerator(seed=42)
        scenarios, _ = generator.generate_pilot_v2_1(safe_count=6, unsafe_count=4)
        
        validator = DatasetValidator(scenarios)
        validator.validate()
        report = validator.report()
        
        self.assertIn("Dataset Validation Report", report)
        self.assertIn("Total scenarios:", report)
        self.assertIn("Label distribution:", report)


class TestDatasetPersistence(unittest.TestCase):
    """Test saving and loading datasets."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        """Clean up temporary files."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_save_and_load_roundtrip(self):
        """Verify scenarios can be saved and loaded without loss."""
        generator = DatasetGenerator(seed=42)
        original_scenarios, _ = generator.generate_pilot_v2_1(safe_count=6, unsafe_count=4)
        
        file_path = self.temp_dir / "test_scenarios.jsonl"
        save_scenarios_to_jsonl(original_scenarios, file_path)
        
        loaded_scenarios = load_scenarios_from_jsonl(file_path)
        
        self.assertEqual(len(original_scenarios), len(loaded_scenarios))
        
        for orig, loaded in zip(original_scenarios, loaded_scenarios):
            self.assertEqual(orig.scenario_id, loaded.scenario_id)
            self.assertEqual(orig.label, loaded.label)
            self.assertEqual(orig.parameters, loaded.parameters)
            self.assertEqual(
                orig.behavioral_features.tool_call_count,
                loaded.behavioral_features.tool_call_count
            )
    
    def test_jsonl_format(self):
        """Verify JSONL file format (one JSON object per line)."""
        generator = DatasetGenerator(seed=42)
        scenarios, _ = generator.generate_pilot_v2_1(safe_count=3, unsafe_count=2)
        
        file_path = self.temp_dir / "test_scenarios.jsonl"
        save_scenarios_to_jsonl(scenarios, file_path)
        
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        
        # Should have same number of lines as scenarios
        self.assertEqual(len(lines), len(scenarios), 
                        f"Should have {len(scenarios)} non-empty lines, got {len(lines)}")
        
        # Each line should be valid JSON
        import json
        for line in lines:
            json.loads(line)  # Should not raise


if __name__ == "__main__":
    unittest.main()
