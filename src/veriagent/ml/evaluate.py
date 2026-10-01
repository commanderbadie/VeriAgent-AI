"""
ML Model Evaluation on Frozen Test Sets
========================================

Evaluates trained models on:
- Frozen test set (44 scenarios)
- Frozen adversarial set (25 scenarios)

CRITICAL: This should only be run ONCE after model selection is final.
"""

import json
from pathlib import Path
from typing import Dict, Any
import numpy as np
import pickle
from datetime import datetime

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


class ModelEvaluator:
    """Evaluates trained models on frozen test sets."""
    
    def __init__(self, model_dir: Path = Path('experiments/outputs/phase5_models')):
        """
        Initialize evaluator.
        
        Args:
            model_dir: Directory containing trained models and preprocessor
        """
        self.model_dir = model_dir
        self.data_dir = Path('data/ml/v1_1')
        
        # Load components
        print("Loading trained components...")
        self.preprocessor = FeaturePreprocessor.load(model_dir / 'preprocessor.json')
        self.extractor = FeatureExtractor()
        
        self.models = {}
        self._load_models()
        
        print(f"  Loaded {len(self.models)} models")
        print(f"  Features: {len(self.preprocessor.get_feature_names())}")
    
    def _load_models(self):
        """Load all trained models."""
        model_files = {
            'logistic_regression': 'logistic_regression.pkl',
            'random_forest': 'random_forest.pkl',
        }
        
        for name, filename in model_files.items():
            filepath = self.model_dir / filename
            if filepath.exists():
                with open(filepath, 'rb') as f:
                    self.models[name] = pickle.load(f)
                print(f"  ✓ {name}")
    
    def evaluate_on_dataset(
        self,
        dataset_file: Path,
        dataset_name: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Evaluate all models on a dataset.
        
        Args:
            dataset_file: Path to JSONL scenario file
            dataset_name: Name for display (e.g., "Test", "Adversarial")
        
        Returns:
            Dict mapping model names to metric dicts
        """
        print("\n" + "="*70)
        print(f"Evaluating on {dataset_name} Set")
        print("="*70)
        
        # Load and prepare data
        features, labels = self.extractor.extract_from_file(dataset_file)
        X = self.preprocessor.transform(features)
        y = convert_labels_to_binary(labels)
        
        print(f"\nDataset: {dataset_file.name}")
        print(f"  Samples: {len(y)}")
        print(f"  SAFE (0): {sum(y == 0)}")
        print(f"  UNSAFE (1): {sum(y == 1)}")
        
        # Evaluate each model
        results = {}
        for model_name, model in self.models.items():
            print(f"\n{'-'*70}")
            print(f"Model: {model_name}")
            print(f"{'-'*70}")
            
            y_pred = model.predict(X)
            y_proba = model.predict_proba(X)[:, 1]
            
            # Compute ROC AUC (handle case where only one class is present)
            try:
                roc_auc = float(roc_auc_score(y, y_proba))
            except ValueError:
                roc_auc = None  # Only one class present
            
            metrics = {
                'accuracy': float(accuracy_score(y, y_pred)),
                'precision': float(precision_score(y, y_pred, zero_division=0)),
                'recall': float(recall_score(y, y_pred, zero_division=0)),
                'f1': float(f1_score(y, y_pred, zero_division=0)),
                'roc_auc': roc_auc,
            }
            
            # Ensure confusion matrix is always 2x2
            cm = confusion_matrix(y, y_pred, labels=[0, 1])
            
            print(f"\nMetrics:")
            print(f"  Accuracy:  {metrics['accuracy']:.4f}")
            print(f"  Precision: {metrics['precision']:.4f}")
            print(f"  Recall:    {metrics['recall']:.4f}")
            print(f"  F1 Score:  {metrics['f1']:.4f}")
            if metrics['roc_auc'] is not None:
                print(f"  ROC AUC:   {metrics['roc_auc']:.4f}")
            else:
                print(f"  ROC AUC:   N/A (only one class)")
            
            print(f"\nConfusion Matrix:")
            print(f"  TN: {cm[0,0]:3d}  FP: {cm[0,1]:3d}")
            print(f"  FN: {cm[1,0]:3d}  TP: {cm[1,1]:3d}")
            
            # Detailed classification report
            print(f"\nClassification Report:")
            try:
                report = classification_report(
                    y, y_pred,
                    target_names=['SAFE', 'UNSAFE'],
                    labels=[0, 1],
                    zero_division=0
                )
                print(report)
            except ValueError as e:
                print(f"  (Skipped: {e})")
            
            results[model_name] = {
                'metrics': metrics,
                'confusion_matrix': {
                    'tn': int(cm[0,0]),
                    'fp': int(cm[0,1]),
                    'fn': int(cm[1,0]),
                    'tp': int(cm[1,1]),
                },
                'predictions': y_pred.tolist(),
                'probabilities': y_proba.tolist(),
            }
        
        return results
    
    def run_final_evaluation(self):
        """Run evaluation on both frozen test sets."""
        print("="*70)
        print("VERIAGENT PHASE 5: FINAL MODEL EVALUATION")
        print("="*70)
        print("\nWARNING: Evaluating on frozen test sets")
        print("This should only be done ONCE after model selection is final.")
        
        # Evaluate on test set
        test_file = self.data_dir / 'scenarios_test_frozen.jsonl'
        test_results = self.evaluate_on_dataset(test_file, "Test")
        
        # Evaluate on adversarial set
        adv_file = self.data_dir / 'scenarios_adversarial_frozen.jsonl'
        adv_results = self.evaluate_on_dataset(adv_file, "Adversarial")
        
        # Summary comparison
        self._print_summary(test_results, adv_results)
        
        # Save results
        self._save_results(test_results, adv_results)
        
        return test_results, adv_results
    
    def _print_summary(
        self,
        test_results: Dict[str, Dict[str, Any]],
        adv_results: Dict[str, Dict[str, Any]]
    ):
        """Print summary comparison table."""
        print("\n" + "="*70)
        print("FINAL EVALUATION SUMMARY")
        print("="*70)
        
        print("\nTest Set Performance:")
        print("-" * 70)
        print(f"{'Model':<20} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1':>10}")
        print("-" * 70)
        
        for model_name in test_results.keys():
            m = test_results[model_name]['metrics']
            print(
                f"{model_name:<20} "
                f"{m['accuracy']:>10.4f} "
                f"{m['precision']:>10.4f} "
                f"{m['recall']:>10.4f} "
                f"{m['f1']:>10.4f}"
            )
        
        print("\nAdversarial Set Performance:")
        print("-" * 70)
        print(f"{'Model':<20} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1':>10}")
        print("-" * 70)
        
        for model_name in adv_results.keys():
            m = adv_results[model_name]['metrics']
            print(
                f"{model_name:<20} "
                f"{m['accuracy']:>10.4f} "
                f"{m['precision']:>10.4f} "
                f"{m['recall']:>10.4f} "
                f"{m['f1']:>10.4f}"
            )
        
        print("-" * 70)
    
    def _save_results(
        self,
        test_results: Dict[str, Dict[str, Any]],
        adv_results: Dict[str, Dict[str, Any]]
    ):
        """Save evaluation results to JSON."""
        results = {
            'evaluation_date': datetime.now().isoformat(),
            'test_set': test_results,
            'adversarial_set': adv_results,
        }
        
        output_file = self.model_dir / 'final_evaluation.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n✓ Evaluation results saved: {output_file}")


def main():
    """Main entry point for evaluation."""
    evaluator = ModelEvaluator()
    evaluator.run_final_evaluation()
    
    print("\n" + "="*70)
    print("EVALUATION COMPLETE")
    print("="*70)


if __name__ == '__main__':
    main()
