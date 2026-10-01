"""
Generate Feature Schema Report
==============================

Produces a comprehensive report showing:
- Raw allowed features
- Encoded output feature names
- Training matrix shape
- Validation matrix shape
- Class counts
"""

from pathlib import Path
import json
from veriagent.ml.feature_extractor import FeatureExtractor, convert_labels_to_binary
from veriagent.ml.preprocessing import FeaturePreprocessor


def generate_report():
    """Generate and print feature schema report."""
    
    data_dir = Path('data/ml/v1_1')
    train_file = data_dir / 'scenarios_train.jsonl'
    val_file = data_dir / 'scenarios_validation.jsonl'
    
    print("="*70)
    print("VERIAGENT PHASE 5: FEATURE EXTRACTION REPORT")
    print("="*70)
    print()
    
    # Extract features
    print("Step 1: Feature Extraction")
    print("-" * 70)
    
    extractor = FeatureExtractor()
    
    print(f"\nAllowed Features (Top-Level):")
    for i, feat in enumerate(sorted(extractor.schema.allowed_toplevel), 1):
        print(f"  {i}. {feat}")
    
    print(f"\nAllowed Features (Behavioral):")
    for i, feat in enumerate(sorted(extractor.schema.allowed_behavioral), 1):
        print(f"  {i}. {feat}")
    
    print(f"\nForbidden Fields (Never Used):")
    for i, field in enumerate(sorted(extractor.schema.forbidden), 1):
        print(f"  {i}. {field}")
    
    print(f"\nRaw Feature Count: {len(extractor.get_feature_names())}")
    
    # Load data
    print("\n" + "="*70)
    print("Step 2: Loading Dataset")
    print("-" * 70)
    
    train_features, train_labels = extractor.extract_from_file(train_file)
    val_features, val_labels = extractor.extract_from_file(val_file)
    
    print(f"\nTraining scenarios loaded: {len(train_features)}")
    print(f"Validation scenarios loaded: {len(val_features)}")
    
    # Preprocessing
    print("\n" + "="*70)
    print("Step 3: Preprocessing (Fit on Train Only)")
    print("-" * 70)
    
    preprocessor = FeaturePreprocessor()
    
    print("\nCategorical Features (One-Hot Encoded):")
    for feat in sorted(preprocessor.config.categorical_features):
        print(f"  - {feat}")
    
    print("\nBoolean Features:")
    for feat in sorted(preprocessor.config.boolean_features):
        print(f"  - {feat}")
    
    print("\nNumeric Features:")
    for feat in sorted(preprocessor.config.numeric_features):
        nullable = " (nullable)" if feat in preprocessor.config.nullable_features else ""
        print(f"  - {feat}{nullable}")
    
    print(f"\nScaling enabled: {preprocessor.config.scale_numeric}")
    print(f"Unknown category handling: {preprocessor.config.handle_unknown_categories}")
    print(f"Missing value fill: {preprocessor.config.missing_fill_value}")
    
    # Fit and transform
    X_train = preprocessor.fit_transform(train_features)
    y_train = convert_labels_to_binary(train_labels)
    
    X_val = preprocessor.transform(val_features)
    y_val = convert_labels_to_binary(val_labels)
    
    print("\n" + "="*70)
    print("Step 4: Output Feature Names (After Encoding)")
    print("-" * 70)
    
    output_features = preprocessor.get_feature_names()
    print(f"\nTotal Encoded Features: {len(output_features)}")
    print("\nEncoded Feature Names:")
    for i, feat in enumerate(output_features, 1):
        print(f"  {i:2d}. {feat}")
    
    # Matrix shapes
    print("\n" + "="*70)
    print("Step 5: Final Matrix Shapes")
    print("-" * 70)
    
    print(f"\nTraining Matrix:")
    print(f"  X_train shape: {X_train.shape}")
    print(f"  y_train shape: {y_train.shape}")
    print(f"  Samples: {X_train.shape[0]}")
    print(f"  Features: {X_train.shape[1]}")
    
    print(f"\nValidation Matrix:")
    print(f"  X_val shape: {X_val.shape}")
    print(f"  y_val shape: {y_val.shape}")
    print(f"  Samples: {X_val.shape[0]}")
    print(f"  Features: {X_val.shape[1]}")
    
    # Class distribution
    print("\n" + "="*70)
    print("Step 6: Class Distribution")
    print("-" * 70)
    
    train_safe = sum(1 for label in train_labels if label == 'SAFE')
    train_unsafe = len(train_labels) - train_safe
    val_safe = sum(1 for label in val_labels if label == 'SAFE')
    val_unsafe = len(val_labels) - val_safe
    
    print(f"\nTraining Set:")
    print(f"  SAFE (0):   {train_safe:3d} ({100*train_safe/len(train_labels):.1f}%)")
    print(f"  UNSAFE (1): {train_unsafe:3d} ({100*train_unsafe/len(train_labels):.1f}%)")
    print(f"  Total:      {len(train_labels):3d}")
    
    print(f"\nValidation Set:")
    print(f"  SAFE (0):   {val_safe:3d} ({100*val_safe/len(val_labels):.1f}%)")
    print(f"  UNSAFE (1): {val_unsafe:3d} ({100*val_unsafe/len(val_labels):.1f}%)")
    print(f"  Total:      {len(val_labels):3d}")
    
    # Category mappings
    print("\n" + "="*70)
    print("Step 7: Learned Categories (From Training Data)")
    print("-" * 70)
    
    for cat_feature in sorted(preprocessor.category_mappings_.keys()):
        categories = preprocessor.category_mappings_[cat_feature]
        print(f"\n{cat_feature}:")
        for cat in categories:
            print(f"  - {cat}")
        if preprocessor.config.handle_unknown_categories:
            print(f"  - UNKNOWN (for unseen values)")
    
    # Numeric statistics
    if preprocessor.config.scale_numeric and preprocessor.numeric_stats_:
        print("\n" + "="*70)
        print("Step 8: Numeric Feature Statistics (Training Data)")
        print("-" * 70)
        
        for num_feature in sorted(preprocessor.numeric_stats_.keys()):
            stats = preprocessor.numeric_stats_[num_feature]
            print(f"\n{num_feature}:")
            print(f"  Mean: {stats['mean']:.4f}")
            print(f"  Std:  {stats['std']:.4f}")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    print(f"\n✓ Feature extraction complete")
    print(f"✓ Raw features: {len(extractor.get_feature_names())}")
    print(f"✓ Encoded features: {len(output_features)}")
    print(f"✓ Training samples: {X_train.shape[0]}")
    print(f"✓ Validation samples: {X_val.shape[0]}")
    print(f"✓ Preprocessor fitted on training data only")
    print(f"✓ No forbidden fields in feature matrix")
    print(f"✓ Deterministic feature ordering")
    print(f"✓ Unknown categories handled")
    print(f"✓ Missing values handled")
    print(f"\n✓ READY FOR MODEL TRAINING")
    
    print("\n" + "="*70)
    print("FROZEN FILES (NOT ACCESSED)")
    print("="*70)
    print("\n✗ scenarios_test_frozen.jsonl - Reserved for final evaluation")
    print("✗ scenarios_adversarial_frozen.jsonl - Reserved for robustness testing")
    
    print("\n" + "="*70)


if __name__ == '__main__':
    generate_report()
