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
        
        scenarios1 = gen1.generate_pilot(count=10)
        scenarios2 = gen2.generate_pilot(count=10)
        
        self.assertEqual(len(scenarios1), len(scenarios2))
        
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
        scenarios = self.generator.generate_pilot(count=20)
        ids = [s.scenario_id for s in scenarios]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate scenario IDs found")
    
    def test_no_leakage_features(self):
        """Verify no prohibited leakage features in parameters."""
        scenarios = self.generator.generate_pilot(count=15)
        
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
        scenarios = self.generator.generate_pilot(count=15)
        
        for scenario in scenarios:
            errors = scenario.validate()
            self.assertEqual(
                len(errors), 0,
                f"Scenario {scenario.scenario_id} validation failed: {errors}"
            )
    
    def test_label_distribution(self):
        """Verify reasonable label distribution."""
        scenarios = self.generator.generate_pilot(count=20)
        
        safe_count = sum(1 for s in scenarios if s.label == ScenarioLabel.SAFE)
        unsafe_count = sum(1 for s in scenarios if s.label == ScenarioLabel.UNSAFE)
        
        # Should have both labels
        self.assertGreater(safe_count, 0, "No SAFE scenarios generated")
        self.assertGreater(unsafe_count, 0, "No UNSAFE scenarios generated")
        
        # Rough balance check (not too extreme)
        safe_ratio = safe_count / len(scenarios)
        self.assertGreater(safe_ratio, 0.3, "Too few SAFE scenarios")
        self.assertLess(safe_ratio, 0.9, "Too few UNSAFE scenarios")
    
    def test_label_justification(self):
        """Verify all scenarios have label reasons."""
        scenarios = self.generator.generate_pilot(count=15)
        
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
        scenarios = self.generator.generate_pilot(count=15)
        
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
        scenarios = self.generator.generate_pilot(count=15)
        
        families = set(s.scenario_family for s in scenarios)
        
        # Should have multiple distinct families
        self.assertGreater(
            len(families), 1,
            "All scenarios have same family (no diversity)"
        )
        
        # Each scenario should have a family
        for scenario in scenarios:
            self.assertTrue(
                scenario.scenario_family,
                f"Scenario {scenario.scenario_id} missing scenario_family"
            )


class TestDatasetValidator(unittest.TestCase):
    """Test dataset validation logic."""
    
    def test_valid_dataset_passes(self):
        """Verify validator accepts valid dataset."""
        generator = DatasetGenerator(seed=42)
        scenarios = generator.generate_pilot(count=10)
        
        validator = DatasetValidator(scenarios)
        is_valid = validator.validate()
        
        self.assertTrue(is_valid, f"Validation failed:\n{validator.report()}")
    
    def test_duplicate_ids_detected(self):
        """Verify validator detects duplicate IDs."""
        generator = DatasetGenerator(seed=42)
        scenarios = generator.generate_pilot(count=5)
        
        # Introduce duplicate
        scenarios.append(scenarios[0])
        
        validator = DatasetValidator(scenarios)
        is_valid = validator.validate()
        
        self.assertFalse(is_valid)
        self.assertTrue(any("Duplicate scenario IDs" in err for err in validator.errors))
    
    def test_validation_report_generation(self):
        """Verify validation report is generated."""
        generator = DatasetGenerator(seed=42)
        scenarios = generator.generate_pilot(count=10)
        
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
        original_scenarios = generator.generate_pilot(count=10)
        
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
        scenarios = generator.generate_pilot(count=5)
        
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
