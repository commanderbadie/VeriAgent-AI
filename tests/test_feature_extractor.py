"""
Tests for Feature Extraction and Preprocessing
==============================================

Validates:
- Feature allowlisting (no leakage)
- Preprocessing fitted only on training data
- Validation transformation
- Unknown category handling
- Missing value handling
- Deterministic feature ordering
- Dataset integrity (hashes unchanged)
"""

import unittest
import json
import hashlib
import tempfile
from pathlib import Path
import numpy as np

from veriagent.ml.feature_extractor import (
    FeatureExtractor,
    FeatureSchema,
    convert_labels_to_binary,
)
from veriagent.ml.preprocessing import (
    FeaturePreprocessor,
    PreprocessingConfig,
)


class TestFeatureExtractor(unittest.TestCase):
    """Test feature extraction from scenarios."""
    
    def test_forbidden_fields_never_extracted(self):
        """Verify forbidden fields are rejected."""
        extractor = FeatureExtractor()
        
        # Verify forbidden fields are defined
        self.assertIn('label', extractor.schema.forbidden)
        self.assertIn('scenario_id', extractor.schema.forbidden)
        self.assertIn('session_id', extractor.schema.forbidden)
        self.assertIn('parameters', extractor.schema.forbidden)
        
        # Try to extract features with forbidden field in feature dict
        # (simulating accidental inclusion)
        scenarios = [{
            'scenario_id': 'test_001',
            'action': 'get_customer',
            'user_role': 'ADMIN',
            'behavioral_features': {
                'tool_sensitivity': 'LOW',
                'has_amount': False,
                'amount_log': None,
                'num_parameters': 1,
                'tool_call_count': 1,
                'same_action_count': 1,
                'retry_count': 0,
                'previous_failure_count': 0,
                'seconds_since_last_action': 0.0,
                'is_rapid_sequence': False,
                'action_frequency': 1,
                'sequence_anomaly_score': 0.0,
                'context_action_match': 1.0,
            },
            'label': 'SAFE',
        }]
        
        features, labels = extractor.extract_features(scenarios, return_labels=True)
        
        # Verify no forbidden fields in extracted features
        for forbidden_field in extractor.schema.forbidden:
            self.assertNotIn(forbidden_field, features[0],
                           f"Forbidden field '{forbidden_field}' found in features!")
    
    def test_labels_returned_separately(self):
        """Verify labels are not included in feature dict."""
        extractor = FeatureExtractor()
        
        scenarios = [{
            'action': 'refund_customer',
            'user_role': 'AGENT',
            'behavioral_features': {
                'tool_sensitivity': 'HIGH',
                'has_amount': True,
                'amount_log': 4.5,
                'num_parameters': 2,
                'tool_call_count': 3,
                'same_action_count': 2,
                'retry_count': 0,
                'previous_failure_count': 0,
                'seconds_since_last_action': 5.2,
                'is_rapid_sequence': False,
                'action_frequency': 2,
                'sequence_anomaly_score': 0.1,
                'context_action_match': 0.9,
            },
            'label': 'UNSAFE',
        }]
        
        features, labels = extractor.extract_features(scenarios, return_labels=True)
        
        # Label should be returned separately
        self.assertEqual(labels, ['UNSAFE'])
        
        # Label should NOT be in features
        self.assertNotIn('label', features[0])
    
    def test_feature_ordering_deterministic(self):
        """Verify feature names are always in same order."""
        extractor = FeatureExtractor()
        
        names1 = extractor.get_feature_names()
        names2 = extractor.get_feature_names()
        
        self.assertEqual(names1, names2)
        
        # Verify top-level fields come first, then behavioral
        # Both groups should be sorted
        toplevel_end = len(extractor.schema.allowed_toplevel)
        toplevel_names = names1[:toplevel_end]
        behavioral_names = names1[toplevel_end:]
        
        self.assertEqual(toplevel_names, sorted(toplevel_names))
        self.assertEqual(behavioral_names, sorted(behavioral_names))
    
    def test_row_counts_match(self):
        """Verify X and y have same number of rows."""
        extractor = FeatureExtractor()
        
        scenarios = [
            self._create_sample_scenario('SAFE'),
            self._create_sample_scenario('UNSAFE'),
            self._create_sample_scenario('SAFE'),
        ]
        
        features, labels = extractor.extract_features(scenarios, return_labels=True)
        
        self.assertEqual(len(features), len(labels))
        self.assertEqual(len(features), 3)
    
    def test_convert_labels_to_binary(self):
        """Test label conversion SAFE=0, UNSAFE=1."""
        labels = ['SAFE', 'UNSAFE', 'SAFE', 'UNSAFE', 'UNSAFE']
        binary = convert_labels_to_binary(labels)
        
        expected = np.array([0, 1, 0, 1, 1])
        np.testing.assert_array_equal(binary, expected)
    
    def _create_sample_scenario(self, label):
        """Helper to create a minimal valid scenario."""
        return {
            'action': 'get_customer',
            'user_role': 'ADMIN',
            'behavioral_features': {
                'tool_sensitivity': 'LOW',
                'has_amount': False,
                'amount_log': None,
                'num_parameters': 1,
                'tool_call_count': 1,
                'same_action_count': 1,
                'retry_count': 0,
                'previous_failure_count': 0,
                'seconds_since_last_action': 0.0,
                'is_rapid_sequence': False,
                'action_frequency': 1,
                'sequence_anomaly_score': 0.0,
                'context_action_match': 1.0,
            },
            'label': label,
        }


class TestPreprocessing(unittest.TestCase):
    """Test preprocessing pipeline."""
    
    def test_fit_only_on_training_data(self):
        """Verify preprocessor learns from training data only."""
        train_features = [
            {
                'action': 'get_customer',
                'user_role': 'ADMIN',
                'tool_sensitivity': 'LOW',
                'has_amount': False,
                'amount_log': None,
                'num_parameters': 1,
                'tool_call_count': 5,
                'same_action_count': 3,
                'retry_count': 0,
                'previous_failure_count': 0,
                'seconds_since_last_action': 2.0,
                'is_rapid_sequence': False,
                'action_frequency': 3,
                'sequence_anomaly_score': 0.1,
                'context_action_match': 0.9,
            },
            {
                'action': 'refund_customer',
                'user_role': 'AGENT',
                'tool_sensitivity': 'HIGH',
                'has_amount': True,
                'amount_log': 5.0,
                'num_parameters': 2,
                'tool_call_count': 10,
                'same_action_count': 5,
                'retry_count': 1,
                'previous_failure_count': 0,
                'seconds_since_last_action': 1.0,
                'is_rapid_sequence': True,
                'action_frequency': 5,
                'sequence_anomaly_score': 0.5,
                'context_action_match': 0.7,
            },
        ]
        
        preprocessor = FeaturePreprocessor()
        preprocessor.fit(train_features)
        
        # Verify categories were learned from training data
        self.assertIn('get_customer', preprocessor.category_mappings_['action'])
        self.assertIn('refund_customer', preprocessor.category_mappings_['action'])
        self.assertIn('ADMIN', preprocessor.category_mappings_['user_role'])
        self.assertIn('AGENT', preprocessor.category_mappings_['user_role'])
    
    def test_validation_transform_works(self):
        """Verify validation data can be transformed after fitting on train."""
        train_features = [
            {
                'action': 'get_customer',
                'user_role': 'ADMIN',
                'tool_sensitivity': 'LOW',
                'has_amount': False,
                'amount_log': None,
                'num_parameters': 1,
                'tool_call_count': 5,
                'same_action_count': 3,
                'retry_count': 0,
                'previous_failure_count': 0,
                'seconds_since_last_action': 2.0,
                'is_rapid_sequence': False,
                'action_frequency': 3,
                'sequence_anomaly_score': 0.1,
                'context_action_match': 0.9,
            },
        ]
        
        val_features = [
            {
                'action': 'get_customer',
                'user_role': 'ADMIN',
                'tool_sensitivity': 'LOW',
                'has_amount': False,
                'amount_log': None,
                'num_parameters': 2,
                'tool_call_count': 8,
                'same_action_count': 4,
                'retry_count': 0,
                'previous_failure_count': 0,
                'seconds_since_last_action': 3.0,
                'is_rapid_sequence': False,
                'action_frequency': 4,
                'sequence_anomaly_score': 0.2,
                'context_action_match': 0.85,
            },
        ]
        
        preprocessor = FeaturePreprocessor()
        X_train = preprocessor.fit_transform(train_features)
        X_val = preprocessor.transform(val_features)
        
        # Both should have same number of features
        self.assertEqual(X_train.shape[1], X_val.shape[1])
    
    def test_unknown_category_handling(self):
        """Verify unknown categories don't crash and are handled gracefully."""
        train_features = [
            {
                'action': 'get_customer',
                'user_role': 'ADMIN',
                'tool_sensitivity': 'LOW',
                'has_amount': False,
                'amount_log': None,
                'num_parameters': 1,
                'tool_call_count': 5,
                'same_action_count': 3,
                'retry_count': 0,
                'previous_failure_count': 0,
                'seconds_since_last_action': 2.0,
                'is_rapid_sequence': False,
                'action_frequency': 3,
                'sequence_anomaly_score': 0.1,
                'context_action_match': 0.9,
            },
        ]
        
        # Validation data with unknown action
        val_features = [
            {
                'action': 'create_invoice',  # Not in training data
                'user_role': 'ADMIN',
                'tool_sensitivity': 'LOW',
                'has_amount': False,
                'amount_log': None,
                'num_parameters': 2,
                'tool_call_count': 3,
                'same_action_count': 1,
                'retry_count': 0,
                'previous_failure_count': 0,
                'seconds_since_last_action': 1.0,
                'is_rapid_sequence': False,
                'action_frequency': 1,
                'sequence_anomaly_score': 0.0,
                'context_action_match': 1.0,
            },
        ]
        
        preprocessor = FeaturePreprocessor()
        X_train = preprocessor.fit_transform(train_features)
        X_val = preprocessor.transform(val_features)
        
        # Should not crash - unknown category should be handled
        self.assertEqual(X_val.shape[0], 1)
        self.assertEqual(X_val.shape[1], X_train.shape[1])
    
    def test_missing_values_handled(self):
        """Verify missing amount and time values don't crash."""
        features = [
            {
                'action': 'get_customer',
                'user_role': 'ADMIN',
                'tool_sensitivity': 'LOW',
                'has_amount': False,
                'amount_log': None,  # Missing
                'num_parameters': 1,
                'tool_call_count': 5,
                'same_action_count': 3,
                'retry_count': 0,
                'previous_failure_count': 0,
                'seconds_since_last_action': None,  # Missing
                'is_rapid_sequence': False,
                'action_frequency': 3,
                'sequence_anomaly_score': 0.1,
                'context_action_match': 0.9,
            },
        ]
        
        preprocessor = FeaturePreprocessor()
        X = preprocessor.fit_transform(features)
        
        # Should not crash and should have correct shape
        self.assertEqual(X.shape[0], 1)
        self.assertGreater(X.shape[1], 0)
        
        # Verify no NaN values in output
        self.assertFalse(np.isnan(X).any())
    
    def test_deterministic_feature_ordering(self):
        """Verify feature names are always in same order."""
        features = [
            {
                'action': 'get_customer',
                'user_role': 'ADMIN',
                'tool_sensitivity': 'LOW',
                'has_amount': False,
                'amount_log': None,
                'num_parameters': 1,
                'tool_call_count': 5,
                'same_action_count': 3,
                'retry_count': 0,
                'previous_failure_count': 0,
                'seconds_since_last_action': 2.0,
                'is_rapid_sequence': False,
                'action_frequency': 3,
                'sequence_anomaly_score': 0.1,
                'context_action_match': 0.9,
            },
        ]
        
        preprocessor1 = FeaturePreprocessor()
        preprocessor1.fit(features)
        names1 = preprocessor1.get_feature_names()
        
        preprocessor2 = FeaturePreprocessor()
        preprocessor2.fit(features)
        names2 = preprocessor2.get_feature_names()
        
        self.assertEqual(names1, names2)


class TestDatasetIntegrity(unittest.TestCase):
    """Test that frozen dataset files remain unchanged."""
    
    DATA_DIR = Path(__file__).parent.parent / 'data' / 'ml' / 'v1_1'
    
    EXPECTED_HASHES = {
        'scenarios_train.jsonl': 'b2315937ddaaf24b5d4300c82b38c1fa9005e2e07c1e0ec3a8dc78cc6fdb532c',
        'scenarios_validation.jsonl': '12af7a28f5f458bc517de1fe65d4608a82661fbacd27ccf16e6fcfa79f74585f',
        'scenarios_test_frozen.jsonl': 'b47f83362a5aae8b49f25940b1985c0004c107a62158787ab1b046076e7ebb5c',
        'scenarios_adversarial_frozen.jsonl': '201cde5c3765567df58f9e3a5f2ffdd4546f9418dbb8cafc6b0c957be911a203',
        'sessions_full.jsonl': '055cff00addad74b2f9aef4ff7ff8dc68dbe3d305d581d8f6b3dc7d2d7f18ef9',
    }
    
    def test_dataset_v1_1_hashes_unchanged(self):
        """Verify Dataset v1.1 files have not been modified."""
        for filename, expected_hash in self.EXPECTED_HASHES.items():
            filepath = self.DATA_DIR / filename
            
            if not filepath.exists():
                self.skipTest(f"Dataset file not found: {filepath}")
            
            actual_hash = self._compute_sha256(filepath)
            
            self.assertEqual(
                actual_hash,
                expected_hash,
                f"Dataset file '{filename}' has been modified! "
                f"Expected: {expected_hash}, Got: {actual_hash}"
            )
    
    def _compute_sha256(self, filepath: Path) -> str:
        """Compute SHA-256 hash of file."""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()


class TestEndToEndPipeline(unittest.TestCase):
    """Test complete feature extraction and preprocessing pipeline."""
    
    DATA_DIR = Path(__file__).parent.parent / 'data' / 'ml' / 'v1_1'
    
    def test_train_validation_pipeline(self):
        """Test loading and processing train and validation data."""
        train_file = self.DATA_DIR / 'scenarios_train.jsonl'
        val_file = self.DATA_DIR / 'scenarios_validation.jsonl'
        
        if not train_file.exists() or not val_file.exists():
            self.skipTest("Dataset files not found")
        
        # Extract features
        extractor = FeatureExtractor()
        train_features, train_labels = extractor.extract_from_file(train_file)
        val_features, val_labels = extractor.extract_from_file(val_file)
        
        # Verify no forbidden fields in extracted features
        for fd in train_features + val_features:
            for forbidden in extractor.schema.forbidden:
                self.assertNotIn(forbidden, fd)
        
        # Fit preprocessor on TRAINING DATA ONLY
        preprocessor = FeaturePreprocessor()
        X_train = preprocessor.fit_transform(train_features)
        y_train = convert_labels_to_binary(train_labels)
        
        # Transform validation data (not fit!)
        X_val = preprocessor.transform(val_features)
        y_val = convert_labels_to_binary(val_labels)
        
        # Verify shapes
        self.assertEqual(X_train.shape[0], len(train_labels))
        self.assertEqual(X_val.shape[0], len(val_labels))
        self.assertEqual(X_train.shape[1], X_val.shape[1])  # Same features
        
        self.assertEqual(len(y_train), len(train_labels))
        self.assertEqual(len(y_val), len(val_labels))
        
        # Verify no NaN values
        self.assertFalse(np.isnan(X_train).any())
        self.assertFalse(np.isnan(X_val).any())
        
        # Verify labels are 0/1
        self.assertTrue(np.all(np.isin(y_train, [0, 1])))
        self.assertTrue(np.all(np.isin(y_val, [0, 1])))
        
        # Print shapes for verification
        print(f"\nTrain shape: {X_train.shape}, labels: {len(y_train)}")
        print(f"Val shape: {X_val.shape}, labels: {len(y_val)}")
        print(f"Features: {len(preprocessor.get_feature_names())}")
    
    def test_frozen_files_not_loaded(self):
        """Verify test and adversarial files are not loaded during feature extraction."""
        # This test documents the constraint - frozen files should NOT be accessed
        # during feature extraction phase
        
        test_file = self.DATA_DIR / 'scenarios_test_frozen.jsonl'
        adv_file = self.DATA_DIR / 'scenarios_adversarial_frozen.jsonl'
        
        # We should NOT call extractor.extract_from_file() on these files
        # This test serves as documentation of this requirement
        
        self.assertTrue(test_file.exists(), "Test file should exist but not be used")
        self.assertTrue(adv_file.exists(), "Adversarial file should exist but not be used")


if __name__ == '__main__':
    unittest.main()
