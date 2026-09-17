"""Generate Pilot v2.2 dataset with integrity fixes."""

import json
from pathlib import Path
from collections import Counter

from veriagent.ml import DatasetGenerator, DatasetValidator
from veriagent.ml.dataset_validator import save_scenarios_to_jsonl


def calculate_feature_stats(scenarios, label_filter=None):
    """Calculate feature statistics for scenarios."""
    filtered = scenarios if label_filter is None else [
        s for s in scenarios if s.label == label_filter
    ]
    
    if not filtered:
        return {}
    
    anomaly_scores = [s.behavioral_features.sequence_anomaly_score for s in filtered]
    context_matches = [s.behavioral_features.context_action_match for s in filtered]
    tool_calls = [s.behavioral_features.tool_call_count for s in filtered]
    
    return {
        "count": len(filtered),
        "anomaly_score_avg": sum(anomaly_scores) / len(anomaly_scores),
        "anomaly_score_min": min(anomaly_scores),
        "anomaly_score_max": max(anomaly_scores),
        "context_match_avg": sum(context_matches) / len(context_matches),
        "context_match_min": min(context_matches),
        "context_match_max": max(context_matches),
        "tool_call_avg": sum(tool_calls) / len(tool_calls),
    }


def main():
    """Generate Pilot v2.2 dataset."""
    print("=" * 70)
    print("Generating Pilot v2.2 Dataset")
    print("=" * 70)
    
    # Initialize generator
    generator = DatasetGenerator(seed=42)
    
    # Generate scenarios
    print("\nGenerating 30 behavioral scenarios (18 SAFE, 12 UNSAFE)...")
    behavioral_scenarios, rules_scenarios = generator.generate_pilot_v2_2(
        safe_count=18,
        unsafe_count=12
    )
    
    print(f"✓ Generated {len(behavioral_scenarios)} behavioral scenarios")
    print(f"✓ Generated {len(rules_scenarios)} rules evaluation scenarios")
    
    # Save scenarios
    data_dir = Path("data/ml")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    behavioral_path = data_dir / "pilot_v2_2_scenarios.jsonl"
    rules_path = data_dir / "rules_evaluation_pilot.jsonl"
    sessions_path = data_dir / "pilot_v2_2_sessions.jsonl"
    
    print(f"\nSaving scenarios to {behavioral_path}...")
    save_scenarios_to_jsonl(behavioral_scenarios, behavioral_path)
    
    print(f"Saving rules scenarios to {rules_path}...")
    save_scenarios_to_jsonl(rules_scenarios, rules_path)
    
    print(f"Saving raw sessions to {sessions_path}...")
    generator.save_sessions(sessions_path)
    
    print(f"✓ Saved {len(generator.generated_sessions)} raw sessions")
    
    # Validate
    print("\n" + "=" * 70)
    print("Validation Report")
    print("=" * 70)
    
    validator = DatasetValidator(behavioral_scenarios)
    is_valid = validator.validate()
    
    print(validator.report())
    
    # Additional statistics
    print("\n" + "=" * 70)
    print("Feature Distribution Analysis")
    print("=" * 70)
    
    from veriagent.ml import ScenarioLabel
    
    safe_stats = calculate_feature_stats(behavioral_scenarios, ScenarioLabel.SAFE)
    unsafe_stats = calculate_feature_stats(behavioral_scenarios, ScenarioLabel.UNSAFE)
    
    print("\nSAFE scenarios:")
    print(f"  Count: {safe_stats['count']}")
    print(f"  Anomaly score: {safe_stats['anomaly_score_avg']:.3f} "
          f"(range: {safe_stats['anomaly_score_min']:.3f}-{safe_stats['anomaly_score_max']:.3f})")
    print(f"  Context match: {safe_stats['context_match_avg']:.3f} "
          f"(range: {safe_stats['context_match_min']:.3f}-{safe_stats['context_match_max']:.3f})")
    print(f"  Avg tool calls: {safe_stats['tool_call_avg']:.1f}")
    
    print("\nUNSAFE scenarios:")
    print(f"  Count: {unsafe_stats['count']}")
    print(f"  Anomaly score: {unsafe_stats['anomaly_score_avg']:.3f} "
          f"(range: {unsafe_stats['anomaly_score_min']:.3f}-{unsafe_stats['anomaly_score_max']:.3f})")
    print(f"  Context match: {unsafe_stats['context_match_avg']:.3f} "
          f"(range: {unsafe_stats['context_match_min']:.3f}-{unsafe_stats['context_match_max']:.3f})")
    print(f"  Avg tool calls: {unsafe_stats['tool_call_avg']:.1f}")
    
    print("\nDistribution overlap (as designed):")
    print(f"  Anomaly score overlap: "
          f"{'YES' if safe_stats['anomaly_score_max'] > unsafe_stats['anomaly_score_min'] else 'NO'}")
    print(f"  Context match overlap: "
          f"{'YES' if safe_stats['context_match_min'] < unsafe_stats['context_match_max'] else 'NO'}")
    
    # Scenario families
    print("\n" + "=" * 70)
    print("Scenario Family Distribution")
    print("=" * 70)
    
    families = Counter(s.scenario_family for s in behavioral_scenarios)
    for family, count in sorted(families.items()):
        print(f"  {family}: {count}")
    
    # Sample scenarios
    print("\n" + "=" * 70)
    print("Sample Scenarios (for manual inspection)")
    print("=" * 70)
    
    print("\nSAFE examples:")
    safe_samples = [s for s in behavioral_scenarios if s.label == ScenarioLabel.SAFE][:3]
    for s in safe_samples:
        print(f"\n  [{s.scenario_id}] {s.scenario_family}")
        print(f"    Action: {s.action}")
        print(f"    User: {s.user_role}")
        print(f"    Reason: {s.label_reason}")
        print(f"    Anomaly: {s.behavioral_features.sequence_anomaly_score:.3f}")
    
    print("\nUNSAFE examples:")
    unsafe_samples = [s for s in behavioral_scenarios if s.label == ScenarioLabel.UNSAFE][:3]
    for s in unsafe_samples:
        print(f"\n  [{s.scenario_id}] {s.scenario_family}")
        print(f"    Action: {s.action}")
        print(f"    User: {s.user_role}")
        print(f"    Reason: {s.label_reason}")
        print(f"    Anomaly: {s.behavioral_features.sequence_anomaly_score:.3f}")
    
    # Summary
    print("\n" + "=" * 70)
    print("Generation Summary")
    print("=" * 70)
    
    if is_valid:
        print("\n✅ All validation checks passed!")
        print(f"✅ Generated {len(behavioral_scenarios)} behavioral scenarios")
        print(f"✅ Generated {len(rules_scenarios)} rules evaluation scenarios")
        print(f"✅ Saved to {behavioral_path}")
        print(f"✅ Sessions saved to {sessions_path}")
        print("\nPilot v2.2 is ready for manual review.")
    else:
        print("\n❌ Validation failed!")
        print("Please review errors above and fix before proceeding.")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
