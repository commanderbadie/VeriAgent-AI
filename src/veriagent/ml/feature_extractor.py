"""
Feature Extraction Module for VeriAgent ML Pipeline
===================================================

Extracts and transforms behavioral features from scenarios into numeric arrays
suitable for ML model training.

CRITICAL: This module enforces feature allowlisting to prevent data leakage.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from dataclasses import dataclass


@dataclass
class FeatureSchema:
    """Defines the allowed features and their transformations."""
    
    # Allowed behavioral features (will be extracted from behavioral_features dict)
    allowed_behavioral: List[str] = None
    
    # Allowed top-level fields
    allowed_toplevel: List[str] = None
    
    # Forbidden fields (will raise error if accessed)
    forbidden: List[str] = None
    
    def __post_init__(self):
        if self.allowed_behavioral is None:
            self.allowed_behavioral = [
                'tool_sensitivity',      # Categorical: LOW, MEDIUM, HIGH
                'has_amount',            # Boolean
                'amount_log',            # Numeric (nullable)
                'num_parameters',        # Numeric
                'tool_call_count',       # Numeric
                'same_action_count',     # Numeric
                'retry_count',           # Numeric
                'previous_failure_count', # Numeric
                'seconds_since_last_action', # Numeric (nullable)
                'is_rapid_sequence',     # Boolean
                'action_frequency',      # Numeric
                'sequence_anomaly_score', # Numeric
                'context_action_match',  # Numeric
            ]
        
        if self.allowed_toplevel is None:
            self.allowed_toplevel = [
                'action',      # Categorical: action name
                'user_role',   # Categorical: ADMIN, AGENT, READ_ONLY
            ]
        
        if self.forbidden is None:
            self.forbidden = [
                'label',
                'label_reason',
                'expected_decision',
                'scenario_id',
                'session_id',
                'split',
                'scenario_family',
                'parameters',  # Raw parameters contain PII/specifics
                'target_event_index',
            ]


class FeatureExtractor:
    """
    Extracts features from scenarios and converts them to numeric arrays.
    
    Key properties:
    - Uses explicit allowlist for features
    - Rejects forbidden fields that could cause leakage
    - Returns labels separately from features
    - Maintains deterministic feature ordering
    """
    
    def __init__(self, schema: Optional[FeatureSchema] = None):
        """
        Initialize feature extractor.
        
        Args:
            schema: FeatureSchema defining allowed/forbidden features.
                   If None, uses default schema.
        """
        self.schema = schema if schema is not None else FeatureSchema()
        self._validate_schema()
    
    def _validate_schema(self):
        """Validate that schema has no overlapping allowed/forbidden fields."""
        allowed_set = set(self.schema.allowed_behavioral + self.schema.allowed_toplevel)
        forbidden_set = set(self.schema.forbidden)
        
        overlap = allowed_set & forbidden_set
        if overlap:
            raise ValueError(f"Schema error: Fields appear in both allowed and forbidden: {overlap}")
    
    def extract_from_file(
        self, 
        filepath: Path,
        return_labels: bool = True
    ) -> Tuple[List[Dict[str, Any]], Optional[List[str]]]:
        """
        Load scenarios from JSONL file and extract features.
        
        Args:
            filepath: Path to JSONL scenario file
            return_labels: If True, return labels separately
        
        Returns:
            Tuple of (feature_dicts, labels) where:
            - feature_dicts: List of dicts with allowed features only
            - labels: List of 'SAFE'/'UNSAFE' strings (or None if return_labels=False)
        
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If forbidden fields are accessed
        """
        scenarios = self._load_scenarios(filepath)
        return self.extract_features(scenarios, return_labels=return_labels)
    
    def _load_scenarios(self, filepath: Path) -> List[Dict]:
        """Load scenarios from JSONL file."""
        if not filepath.exists():
            raise FileNotFoundError(f"Scenario file not found: {filepath}")
        
        scenarios = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    scenarios.append(json.loads(line))
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON at line {line_num}: {e}")
        
        return scenarios
    
    def extract_features(
        self,
        scenarios: List[Dict],
        return_labels: bool = True
    ) -> Tuple[List[Dict[str, Any]], Optional[List[str]]]:
        """
        Extract allowed features from scenario dicts.
        
        Args:
            scenarios: List of scenario dictionaries
            return_labels: If True, extract and return labels separately
        
        Returns:
            Tuple of (feature_dicts, labels)
        """
        feature_dicts = []
        labels = [] if return_labels else None
        
        for i, scenario in enumerate(scenarios):
            try:
                # Extract label first (if requested)
                if return_labels:
                    label = scenario.get('label')
                    if label not in ['SAFE', 'UNSAFE']:
                        raise ValueError(f"Invalid label: {label}")
                    labels.append(label)
                
                # Build feature dict
                features = {}
                
                # Extract top-level allowed fields
                for field in self.schema.allowed_toplevel:
                    if field not in scenario:
                        raise ValueError(f"Required field '{field}' missing in scenario {i}")
                    features[field] = scenario[field]
                
                # Extract behavioral features
                behavioral = scenario.get('behavioral_features', {})
                if not behavioral:
                    raise ValueError(f"Missing 'behavioral_features' in scenario {i}")
                
                for field in self.schema.allowed_behavioral:
                    if field not in behavioral:
                        raise ValueError(f"Required behavioral feature '{field}' missing in scenario {i}")
                    features[field] = behavioral[field]
                
                # Verify no forbidden fields leaked into features
                self._check_no_leakage(features)
                
                feature_dicts.append(features)
            
            except Exception as e:
                raise ValueError(f"Error extracting features from scenario {i}: {e}")
        
        return feature_dicts, labels
    
    def _check_no_leakage(self, features: Dict[str, Any]):
        """Verify no forbidden fields are present in extracted features."""
        forbidden_found = [f for f in self.schema.forbidden if f in features]
        if forbidden_found:
            raise ValueError(f"LEAKAGE DETECTED: Forbidden fields found in features: {forbidden_found}")
    
    def get_feature_names(self) -> List[str]:
        """
        Get ordered list of raw feature names (before encoding).
        
        Returns:
            List of feature names in deterministic order
        """
        # Deterministic order: top-level first (alphabetically), then behavioral (alphabetically)
        return (
            sorted(self.schema.allowed_toplevel) + 
            sorted(self.schema.allowed_behavioral)
        )
    
    def validate_scenarios(self, scenarios: List[Dict]) -> Dict[str, Any]:
        """
        Validate scenarios without extracting features.
        
        Returns:
            Dict with validation results
        """
        results = {
            'total_scenarios': len(scenarios),
            'valid_scenarios': 0,
            'errors': [],
            'label_distribution': {'SAFE': 0, 'UNSAFE': 0},
        }
        
        for i, scenario in enumerate(scenarios):
            try:
                # Check label
                label = scenario.get('label')
                if label not in ['SAFE', 'UNSAFE']:
                    results['errors'].append(f"Scenario {i}: Invalid label '{label}'")
                    continue
                results['label_distribution'][label] += 1
                
                # Check required fields
                for field in self.schema.allowed_toplevel:
                    if field not in scenario:
                        results['errors'].append(f"Scenario {i}: Missing field '{field}'")
                        continue
                
                behavioral = scenario.get('behavioral_features', {})
                if not behavioral:
                    results['errors'].append(f"Scenario {i}: Missing 'behavioral_features'")
                    continue
                
                for field in self.schema.allowed_behavioral:
                    if field not in behavioral:
                        results['errors'].append(f"Scenario {i}: Missing behavioral feature '{field}'")
                        continue
                
                results['valid_scenarios'] += 1
            
            except Exception as e:
                results['errors'].append(f"Scenario {i}: {str(e)}")
        
        return results


def convert_labels_to_binary(labels: List[str]) -> np.ndarray:
    """
    Convert SAFE/UNSAFE labels to binary (0/1).
    
    Args:
        labels: List of 'SAFE' or 'UNSAFE' strings
    
    Returns:
        Numpy array of 0 (SAFE) and 1 (UNSAFE)
    """
    label_map = {'SAFE': 0, 'UNSAFE': 1}
    return np.array([label_map[label] for label in labels])
