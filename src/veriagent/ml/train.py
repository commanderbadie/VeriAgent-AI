"""
ML Model Training for VeriAgent Phase 5
========================================

Trains baseline classifiers:
- Logistic Regression
- Random Forest

Uses ONLY training and validation data.
Frozen test/adversarial data are reserved for final evaluation.
"""

import json
from pathlib import Path
from typing import Dict, Any, Tuple
import numpy as np
from dataclasses import dataclass
import pickle

# Scikit-learn imports
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)

from veriagent.ml.feature_extractor import FeatureExtractor, convert_labels_to_binary
from veriagent.ml.preprocessing import FeaturePreprocessor


@dataclass
class TrainingConfig:
    """Configuration for model training."""
    
    # Data paths
    data_dir: Path = Path('data/ml/v1_1')
    output_dir: Path = Path('experiments/outputs/phase5_models')
    
    # Model hyperparameters
    logistic_regression_params: Dict[str, Any] = None
    random_forest_params: Dict[str, Any] = None
    
    # Random seed for reproducibility
    random_seed: int = 42
    
    def __post_init__(self):
        if self.logistic_regression_params is None:
            self.logistic_regression_params = {
                'max_iter': 1000,
                'random_state': self.random_seed,
                'class_weight': 'balanced',  # Handle class imbalance
                'solver': 'lbfgs',
            }
        
        if self.random_forest_params is None:
            self.random_forest_params = {
                'n_estimators': 100,
                'max_depth': 10,
                'min_samples_split': 5,
                'min_samples_leaf': 2,
                'random_state': self.random_seed,
                'class_weight': 'balanced',
                'n_jobs': -1,  # Use all CPU cores
            }


class ModelTrainer:
    """Trains and evaluates ML models for behavioral verification."""
    
    def __init__(self, config: TrainingConfig = None):
        """
        Initialize trainer.
        
        Args:
            config: TrainingConfig with paths and hyperparameters
        """
        self.config = config if config is not None else TrainingConfig()
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Will be populated during training
        self.extractor = None
        self.preprocessor = None
        self.models = {}
        self.metrics = {}
    
    def load_and_prepare_data(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Load training and validation data.
        
        Returns:
            Tuple of (X_train, y_train, X_val, y_val)
        """
        print("Loading data...")
        
        train_file = self.config.data_dir / 'scenarios_train.jsonl'
        val_file = self.config.data_dir / 'scenarios_validation.jsonl'
        
        # Extract features
        self.extractor = FeatureExtractor()
        
        train_features, train_labels = self.extractor.extract_from_file(train_file)
        val_features, val_labels = self.extractor.extract_from_file(val_file)
        
        print(f"  Training scenarios: {len(train_features)}")
        print(f"  Validation scenarios: {len(val_features)}")
        
        # Preprocess (fit on training data only!)
        print("\nPreprocessing features...")
        self.preprocessor = FeaturePreprocessor()
        
        X_train = self.preprocessor.fit_transform(train_features)
        y_train = convert_labels_to_binary(train_labels)
        
        X_val = self.preprocessor.transform(val_features)
        y_val = convert_labels_to_binary(val_labels)
        
        print(f"  X_train shape: {X_train.shape}")
        print(f"  X_val shape: {X_val.shape}")
        print(f"  Features: {X_train.shape[1]}")
        
        return X_train, y_train, X_val, y_val
    
    def train_logistic_regression(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray
    ):
        """Train Logistic Regression model."""
        print("\n" + "="*70)
        print("Training Logistic Regression")
        print("="*70)
        
        model = LogisticRegression(**self.config.logistic_regression_params)
        model.fit(X_train, y_train)
        
        self.models['logistic_regression'] = model
        
        # Evaluate
        train_metrics = self._evaluate_model(model, X_train, y_train, "Training")
        val_metrics = self._evaluate_model(model, X_val, y_val, "Validation")
        
        self.metrics['logistic_regression'] = {
            'train': train_metrics,
            'validation': val_metrics,
        }
        
        # Save model
        model_path = self.config.output_dir / 'logistic_regression.pkl'
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        print(f"\nModel saved: {model_path}")
        
        return model
    
    def train_random_forest(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray
    ):
        """Train Random Forest model."""
        print("\n" + "="*70)
        print("Training Random Forest")
        print("="*70)
        
        model = RandomForestClassifier(**self.config.random_forest_params)
        model.fit(X_train, y_train)
        
        self.models['random_forest'] = model
        
        # Evaluate
        train_metrics = self._evaluate_model(model, X_train, y_train, "Training")
        val_metrics = self._evaluate_model(model, X_val, y_val, "Validation")
        
        self.metrics['random_forest'] = {
            'train': train_metrics,
            'validation': val_metrics,
        }
        
        # Save model
        model_path = self.config.output_dir / 'random_forest.pkl'
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        print(f"\nModel saved: {model_path}")
        
        return model
    
    def _evaluate_model(
        self,
        model,
        X: np.ndarray,
        y: np.ndarray,
        dataset_name: str
    ) -> Dict[str, float]:
        """
        Evaluate model and print metrics.
        
        Args:
            model: Trained sklearn model
            X: Feature matrix
            y: True labels (0/1)
            dataset_name: Name for display (e.g., "Training", "Validation")
        
        Returns:
            Dict of metric names to values
        """
        y_pred = model.predict(X)
        y_proba = model.predict_proba(X)[:, 1]  # Probability of UNSAFE
        
        metrics = {
            'accuracy': accuracy_score(y, y_pred),
            'precision': precision_score(y, y_pred, zero_division=0),
            'recall': recall_score(y, y_pred, zero_division=0),
            'f1': f1_score(y, y_pred, zero_division=0),
            'roc_auc': roc_auc_score(y, y_proba),
        }
        
        cm = confusion_matrix(y, y_pred)
        
        print(f"\n{dataset_name} Metrics:")
        print(f"  Accuracy:  {metrics['accuracy']:.4f}")
        print(f"  Precision: {metrics['precision']:.4f}")
        print(f"  Recall:    {metrics['recall']:.4f}")
        print(f"  F1 Score:  {metrics['f1']:.4f}")
        print(f"  ROC AUC:   {metrics['roc_auc']:.4f}")
        
        print(f"\nConfusion Matrix:")
        print(f"  TN: {cm[0,0]:3d}  FP: {cm[0,1]:3d}")
        print(f"  FN: {cm[1,0]:3d}  TP: {cm[1,1]:3d}")
        
        return metrics
    
    def compare_models(self):
        """Print comparison table of all trained models."""
        print("\n" + "="*70)
        print("MODEL COMPARISON")
        print("="*70)
        
        if not self.metrics:
            print("No models trained yet.")
            return
        
        print("\nValidation Set Performance:")
        print("-" * 70)
        print(f"{'Model':<20} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1':>10} {'ROC AUC':>10}")
        print("-" * 70)
        
        for model_name, metrics in self.metrics.items():
            val_metrics = metrics['validation']
            print(
                f"{model_name:<20} "
                f"{val_metrics['accuracy']:>10.4f} "
                f"{val_metrics['precision']:>10.4f} "
                f"{val_metrics['recall']:>10.4f} "
                f"{val_metrics['f1']:>10.4f} "
                f"{val_metrics['roc_auc']:>10.4f}"
            )
        
        print("-" * 70)
        
        # Identify best model
        best_model_name = max(
            self.metrics.keys(),
            key=lambda name: self.metrics[name]['validation']['f1']
        )
        print(f"\nBest Model (by F1): {best_model_name}")
        print(f"Validation F1: {self.metrics[best_model_name]['validation']['f1']:.4f}")
    
    def save_results(self):
        """Save training results and metrics to JSON."""
        results = {
            'config': {
                'random_seed': self.config.random_seed,
                'logistic_regression_params': self.config.logistic_regression_params,
                'random_forest_params': self.config.random_forest_params,
            },
            'feature_count': len(self.preprocessor.get_feature_names()),
            'feature_names': self.preprocessor.get_feature_names(),
            'models': self.metrics,
        }
        
        results_path = self.config.output_dir / 'training_results.json'
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved: {results_path}")
        
        # Save preprocessor
        preprocessor_path = self.config.output_dir / 'preprocessor.json'
        self.preprocessor.save(preprocessor_path)
        print(f"Preprocessor saved: {preprocessor_path}")
    
    def run_training_pipeline(self):
        """Run complete training pipeline."""
        print("="*70)
        print("VERIAGENT PHASE 5: ML MODEL TRAINING")
        print("="*70)
        
        # Load data
        X_train, y_train, X_val, y_val = self.load_and_prepare_data()
        
        # Train models
        self.train_logistic_regression(X_train, y_train, X_val, y_val)
        self.train_random_forest(X_train, y_train, X_val, y_val)
        
        # Compare
        self.compare_models()
        
        # Save everything
        self.save_results()
        
        print("\n" + "="*70)
        print("TRAINING COMPLETE")
        print("="*70)
        print("\n✓ Models trained and saved")
        print("✓ Metrics computed on train and validation sets")
        print("✓ Frozen test/adversarial sets NOT used (reserved for final evaluation)")
        print(f"✓ All outputs saved to: {self.config.output_dir}")


def main():
    """Main entry point for training."""
    trainer = ModelTrainer()
    trainer.run_training_pipeline()


if __name__ == '__main__':
    main()
