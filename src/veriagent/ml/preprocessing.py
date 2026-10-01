"""
Preprocessing Pipeline for VeriAgent ML Features
================================================

Handles:
- Missing value imputation
- Categorical encoding (one-hot)
- Unknown category handling
- Numeric scaling
- Deterministic feature ordering

CRITICAL: Preprocessing must be fitted ONLY on training data.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import numpy as np
from dataclasses import dataclass, field


@dataclass
class PreprocessingConfig:
    """Configuration for preprocessing pipeline."""
    
    # Categorical features (will be one-hot encoded)
    categorical_features: List[str] = field(default_factory=lambda: [
        'action',
        'user_role',
        'tool_sensitivity',
    ])
    
    # Boolean features (will be converted to 0/1)
    boolean_features: List[str] = field(default_factory=lambda: [
        'has_amount',
        'is_rapid_sequence',
    ])
    
    # Numeric features (will be scaled if scale_numeric=True)
    numeric_features: List[str] = field(default_factory=lambda: [
        'amount_log',
        'num_parameters',
        'tool_call_count',
        'same_action_count',
        'retry_count',
        'previous_failure_count',
        'seconds_since_last_action',
        'action_frequency',
        'sequence_anomaly_score',
        'context_action_match',
    ])
    
    # Features that can be null/missing
    nullable_features: List[str] = field(default_factory=lambda: [
        'amount_log',
        'seconds_since_last_action',
    ])
    
    # Fill value for missing numeric features
    missing_fill_value: float = 0.0
    
    # Whether to apply standard scaling to numeric features
    scale_numeric: bool = True
    
    # Handle unknown categories by adding 'UNKNOWN' category
    handle_unknown_categories: bool = True


class FeaturePreprocessor:
    """
    Preprocesses raw features into numeric arrays.
    
    Key properties:
    - Fitted only on training data
    - Handles unknown categories gracefully
    - Maintains deterministic feature ordering
    - Separate handling for categorical, boolean, and numeric features
    """
    
    def __init__(self, config: Optional[PreprocessingConfig] = None):
        """
        Initialize preprocessor.
        
        Args:
            config: PreprocessingConfig with feature definitions
        """
        self.config = config if config is not None else PreprocessingConfig()
        
        # Will be populated during fit()
        self.is_fitted = False
        self.category_mappings_: Optional[Dict[str, List[str]]] = None
        self.numeric_stats_: Optional[Dict[str, Dict[str, float]]] = None
        self.output_feature_names_: Optional[List[str]] = None
    
    def fit(self, feature_dicts: List[Dict[str, Any]]) -> 'FeaturePreprocessor':
        """
        Fit preprocessor on training data.
        
        CRITICAL: This must ONLY be called on training data, never on
        validation or test data.
        
        Args:
            feature_dicts: List of feature dictionaries (from FeatureExtractor)
        
        Returns:
            self (for chaining)
        """
        if not feature_dicts:
            raise ValueError("Cannot fit on empty feature list")
        
        # Learn categorical mappings
        self.category_mappings_ = {}
        for cat_feature in self.config.categorical_features:
            unique_values = set()
            for fd in feature_dicts:
                val = fd.get(cat_feature)
                if val is not None:
                    unique_values.add(val)
            
            # Sort for deterministic ordering
            self.category_mappings_[cat_feature] = sorted(unique_values)
        
        # Learn numeric statistics (for scaling)
        self.numeric_stats_ = {}
        if self.config.scale_numeric:
            for num_feature in self.config.numeric_features:
                values = []
                for fd in feature_dicts:
                    val = fd.get(num_feature)
                    # Skip nulls when computing stats
                    if val is not None and not (isinstance(val, float) and np.isnan(val)):
                        values.append(float(val))
                
                if values:
                    self.numeric_stats_[num_feature] = {
                        'mean': float(np.mean(values)),
                        'std': float(np.std(values)),
                    }
                else:
                    # No valid values found, use defaults
                    self.numeric_stats_[num_feature] = {
                        'mean': 0.0,
                        'std': 1.0,
                    }
        
        # Build output feature names
        self.output_feature_names_ = self._build_output_feature_names()
        
        self.is_fitted = True
        return self
    
    def _build_output_feature_names(self) -> List[str]:
        """Build deterministic list of output feature names after encoding."""
        names = []
        
        # Categorical features (one-hot encoded)
        for cat_feature in sorted(self.config.categorical_features):
            categories = self.category_mappings_[cat_feature]
            for category in categories:
                names.append(f"{cat_feature}_{category}")
            # Add unknown category if enabled
            if self.config.handle_unknown_categories:
                names.append(f"{cat_feature}_UNKNOWN")
        
        # Boolean features (as-is)
        for bool_feature in sorted(self.config.boolean_features):
            names.append(bool_feature)
        
        # Numeric features (as-is, possibly scaled)
        for num_feature in sorted(self.config.numeric_features):
            names.append(num_feature)
        
        return names
    
    def transform(self, feature_dicts: List[Dict[str, Any]]) -> np.ndarray:
        """
        Transform feature dicts to numeric array.
        
        Args:
            feature_dicts: List of feature dictionaries
        
        Returns:
            Numpy array of shape (n_samples, n_features)
        
        Raises:
            RuntimeError: If called before fit()
        """
        if not self.is_fitted:
            raise RuntimeError("Preprocessor must be fitted before transform()")
        
        if not feature_dicts:
            raise ValueError("Cannot transform empty feature list")
        
        n_samples = len(feature_dicts)
        n_features = len(self.output_feature_names_)
        
        X = np.zeros((n_samples, n_features), dtype=np.float64)
        
        for i, fd in enumerate(feature_dicts):
            feature_idx = 0
            
            # Encode categorical features
            for cat_feature in sorted(self.config.categorical_features):
                categories = self.category_mappings_[cat_feature]
                value = fd.get(cat_feature)
                
                # One-hot encode
                for category in categories:
                    if value == category:
                        X[i, feature_idx] = 1.0
                    feature_idx += 1
                
                # Handle unknown category
                if self.config.handle_unknown_categories:
                    if value not in categories and value is not None:
                        X[i, feature_idx] = 1.0  # Mark as unknown
                    feature_idx += 1
            
            # Encode boolean features
            for bool_feature in sorted(self.config.boolean_features):
                value = fd.get(bool_feature)
                if value is True:
                    X[i, feature_idx] = 1.0
                elif value is False:
                    X[i, feature_idx] = 0.0
                else:
                    # Missing boolean treated as False
                    X[i, feature_idx] = 0.0
                feature_idx += 1
            
            # Encode numeric features
            for num_feature in sorted(self.config.numeric_features):
                value = fd.get(num_feature)
                
                # Handle missing/null values
                if value is None or (isinstance(value, float) and np.isnan(value)):
                    if num_feature in self.config.nullable_features:
                        value = self.config.missing_fill_value
                    else:
                        raise ValueError(f"Unexpected missing value for non-nullable feature '{num_feature}' at sample {i}")
                
                value = float(value)
                
                # Apply scaling if enabled
                if self.config.scale_numeric:
                    stats = self.numeric_stats_[num_feature]
                    std = stats['std']
                    if std > 0:
                        value = (value - stats['mean']) / std
                    else:
                        value = 0.0  # Constant feature
                
                X[i, feature_idx] = value
                feature_idx += 1
        
        return X
    
    def fit_transform(self, feature_dicts: List[Dict[str, Any]]) -> np.ndarray:
        """
        Fit preprocessor and transform in one step.
        
        Args:
            feature_dicts: List of feature dictionaries (training data)
        
        Returns:
            Numpy array of shape (n_samples, n_features)
        """
        self.fit(feature_dicts)
        return self.transform(feature_dicts)
    
    def get_feature_names(self) -> List[str]:
        """
        Get list of output feature names (after encoding).
        
        Returns:
            List of feature names
        
        Raises:
            RuntimeError: If called before fit()
        """
        if not self.is_fitted:
            raise RuntimeError("Preprocessor must be fitted before getting feature names")
        return self.output_feature_names_.copy()
    
    def save(self, filepath: Path):
        """
        Save fitted preprocessor to JSON file.
        
        Args:
            filepath: Path to save file
        """
        if not self.is_fitted:
            raise RuntimeError("Cannot save unfitted preprocessor")
        
        data = {
            'config': {
                'categorical_features': self.config.categorical_features,
                'boolean_features': self.config.boolean_features,
                'numeric_features': self.config.numeric_features,
                'nullable_features': self.config.nullable_features,
                'missing_fill_value': self.config.missing_fill_value,
                'scale_numeric': self.config.scale_numeric,
                'handle_unknown_categories': self.config.handle_unknown_categories,
            },
            'category_mappings': self.category_mappings_,
            'numeric_stats': self.numeric_stats_,
            'output_feature_names': self.output_feature_names_,
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load(cls, filepath: Path) -> 'FeaturePreprocessor':
        """
        Load fitted preprocessor from JSON file.
        
        Args:
            filepath: Path to saved file
        
        Returns:
            Fitted FeaturePreprocessor
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Reconstruct config
        config = PreprocessingConfig(
            categorical_features=data['config']['categorical_features'],
            boolean_features=data['config']['boolean_features'],
            numeric_features=data['config']['numeric_features'],
            nullable_features=data['config']['nullable_features'],
            missing_fill_value=data['config']['missing_fill_value'],
            scale_numeric=data['config']['scale_numeric'],
            handle_unknown_categories=data['config']['handle_unknown_categories'],
        )
        
        # Create preprocessor and restore state
        preprocessor = cls(config=config)
        preprocessor.category_mappings_ = data['category_mappings']
        preprocessor.numeric_stats_ = data['numeric_stats']
        preprocessor.output_feature_names_ = data['output_feature_names']
        preprocessor.is_fitted = True
        
        return preprocessor
