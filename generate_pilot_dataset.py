#!/usr/bin/env python3
"""Generate pilot dataset for inspection and validation."""

from pathlib import Path
import json

from src.veriagent.ml import DatasetGenerator, DatasetValidator
from src.veriagent.ml.dataset_validator import save_scenarios_to_jsonl


def main():
    """Generate pilot dataset v2.1."""
    print("=" * 70)
    print("VeriAgent ML Pilot Dataset Generation v2.1")
    print("=" * 70)
    
    # Initialize generator with fixed seed
    generator = DatasetGenerator(seed=42)
    print("\n✓ Generator initialized with seed=42")
    
    # Generate pilot scenarios with explicit quotas
    safe_count = 18
    unsafe_count = 12
    total_count = safe_count + unsafe_count
    
    print(f"\n📊 Generating pilot scenarios with explicit quotas:")
    print(f"   SAFE: {safe_count}")
    print(f"   UNSAFE: {unsafe_count}")
    print(f"   Total behavioral: {total_count}")
    
    behavioral_scenarios, rules_scenarios = generator.generate_pilot_v2_1(
        safe_count=safe_count,
        unsafe_count=unsafe_count
    )
    
    print(f"\n✓ Generated {len(behavioral_scenarios)} behavioral scenarios")
    print(f"✓ Generated {len(rules_scenarios)} rules-evaluation scenarios")
    
    # Verify counts
    actual_safe = sum(1 for s in behavioral_scenarios if s.label.value == "SAFE")
    actual_unsafe = sum(1 for s in behavioral_scenarios if s.label.value == "UNSAFE")
    
    if actual_safe != safe_count or actual_unsafe != unsafe_count:
        print(f"\n⚠️  WARNING: Quota mismatch!")
        print(f"   Expected SAFE: {safe_count}, Got: {actual_safe}")
        print(f"   Expected UNSAFE: {unsafe_count}, Got: {actual_unsafe}")
    else:
        print(f"✓ Exact quotas met: {actual_safe} SAFE, {actual_unsafe} UNSAFE")
    
    # Validate behavioral dataset
    print("\n🔍 Validating behavioral dataset...")
    validator = DatasetValidator(behavioral_scenarios)
    is_valid = validator.validate()
    
    print(validator.report())
    
    if not is_valid:
        print("\n❌ Validation failed! Fix errors before proceeding.")
        return 1
    
    if validator.warnings:
        print(f"\n⚠️  {len(validator.warnings)} warnings found - must fix before v2.1 approval")
    
    # Save behavioral scenarios
    output_path = Path("data/ml/pilot_v2_1_scenarios.jsonl")
    print(f"\n💾 Saving behavioral scenarios to {output_path}...")
    save_scenarios_to_jsonl(behavioral_scenarios, output_path)
    print(f"✓ Saved {len(behavioral_scenarios)} scenarios")
    
    # Save rules evaluation scenarios
    rules_path = Path("data/ml/rules_evaluation_pilot.jsonl")
    print(f"\n💾 Saving rules-evaluation scenarios to {rules_path}...")
    save_scenarios_to_jsonl(rules_scenarios, rules_path)
    print(f"✓ Saved {len(rules_scenarios)} scenarios")
    
    # Analyze feature distributions
    safe_scenarios = [s for s in behavioral_scenarios if s.label.value == "SAFE"]
    unsafe_scenarios = [s for s in behavioral_scenarios if s.label.value == "UNSAFE"]
    
    # Create manifest
    manifest = {
        "dataset_type": "pilot_v2.1",
        "behavioral_scenarios": len(behavioral_scenarios),
        "rules_evaluation_scenarios": len(rules_scenarios),
        "seed": generator.seed,
        "label_distribution": {
            "SAFE": len(safe_scenarios),
            "UNSAFE": len(unsafe_scenarios),
        },
        "scenario_families": list(set(s.scenario_family for s in behavioral_scenarios)),
        "feature_count": 14,
        "generated_by": "DatasetGenerator v2.1",
        "improvements_over_v2": [
            "Explicit quotas (18 SAFE, 12 UNSAFE)",
            "Real counterexamples (legitimate rapid vs slow enumeration)",
            "Anomaly scores computed from raw events",
            "Deterministic failures moved to separate file",
            "Duplicate detection based on model inputs only",
            "Genuine multi-event sessions",
            "Expanded customer ID range (101-120)"
        ]
    }
    
    manifest_path = Path("data/ml/pilot_v2_1_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"✓ Saved manifest to {manifest_path}")
    
    # Feature distribution report
    print("\n📊 Feature Distribution Analysis:")
    print(f"\nLabel distribution (behavioral only):")
    print(f"  SAFE: {len(safe_scenarios)} ({100*len(safe_scenarios)/len(behavioral_scenarios):.1f}%)")
    print(f"  UNSAFE: {len(unsafe_scenarios)} ({100*len(unsafe_scenarios)/len(behavioral_scenarios):.1f}%)")
    
    print(f"\nScenario families ({len(manifest['scenario_families'])} unique):")
    family_counts = {}
    for s in behavioral_scenarios:
        family_counts[s.scenario_family] = family_counts.get(s.scenario_family, 0) + 1
    for family, count in sorted(family_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  {family}: {count}")
    
    # Feature stats with overlap analysis
    safe_anomaly_scores = [s.behavioral_features.sequence_anomaly_score for s in safe_scenarios]
    unsafe_anomaly_scores = [s.behavioral_features.sequence_anomaly_score for s in unsafe_scenarios]
    
    safe_anomaly_avg = sum(safe_anomaly_scores) / len(safe_anomaly_scores)
    unsafe_anomaly_avg = sum(unsafe_anomaly_scores) / len(unsafe_anomaly_scores)
    safe_anomaly_max = max(safe_anomaly_scores)
    unsafe_anomaly_min = min(unsafe_anomaly_scores)
    
    print(f"\nSequence anomaly score distribution:")
    print(f"  SAFE:   avg={safe_anomaly_avg:.3f}, max={safe_anomaly_max:.3f}")
    print(f"  UNSAFE: avg={unsafe_anomaly_avg:.3f}, min={unsafe_anomaly_min:.3f}")
    print(f"  Separation: {unsafe_anomaly_avg - safe_anomaly_avg:.3f}")
    if safe_anomaly_max > unsafe_anomaly_min:
        print(f"  ✓ Overlap detected: some SAFE > some UNSAFE (good!)")
    else:
        print(f"  ⚠️  No overlap: distributions too clean (needs counterexamples)")
    
    # Context match
    safe_context = [s.behavioral_features.context_action_match for s in safe_scenarios]
    unsafe_context = [s.behavioral_features.context_action_match for s in unsafe_scenarios]
    
    print(f"\nContext-action match distribution:")
    print(f"  SAFE:   avg={sum(safe_context)/len(safe_context):.3f}")
    print(f"  UNSAFE: avg={sum(unsafe_context)/len(unsafe_context):.3f}")
    
    # Sample output
    print("\n📋 Sample scenarios (first 3 behavioral):")
    for i, scenario in enumerate(behavioral_scenarios[:3], 1):
        print(f"\n[{i}] {scenario.scenario_id} ({scenario.label.value})")
        print(f"    Family: {scenario.scenario_family}")
        print(f"    Action: {scenario.action} (role: {scenario.user_role})")
        print(f"    Expected: {scenario.expected_decision.value if scenario.expected_decision else 'N/A'}")
        print(f"    Anomaly: {scenario.behavioral_features.sequence_anomaly_score:.3f}")
        print(f"    Reason: {scenario.label_reason}")
    
    print("\n📋 Sample rules-evaluation scenarios:")
    for i, scenario in enumerate(rules_scenarios[:2], 1):
        print(f"\n[{i}] {scenario.scenario_id}")
        print(f"    Action: {scenario.action}")
        print(f"    Reason: {scenario.label_reason}")
    
    print("\n" + "=" * 70)
    print("✅ Pilot v2.1 dataset generation complete!")
    print("=" * 70)
    
    # Acceptance gate checklist
    print("\n📋 Acceptance Gate Checklist:")
    checks = [
        (len(behavioral_scenarios) == total_count, f"Exactly {total_count} behavioral scenarios"),
        (actual_safe == safe_count and actual_unsafe == unsafe_count, f"Exactly {safe_count} SAFE and {unsafe_count} UNSAFE"),
        (len(validator.warnings) == 0, "Zero duplicate warnings"),
        (len(set(s.user_role for s in behavioral_scenarios) & {"ADMIN", "AGENT", "READ_ONLY"}) > 0, "Correct VeriAgent roles"),
        (len(rules_scenarios) > 0, "Deterministic failures separated"),
        (len(manifest['scenario_families']) >= 10, "At least 10 unique families (counterexamples)"),
        (safe_anomaly_max > unsafe_anomaly_min, "Overlapping anomaly scores"),
    ]
    
    all_pass = True
    for passed, description in checks:
        status = "✅" if passed else "❌"
        print(f"  {status} {description}")
        if not passed:
            all_pass = False
    
    if all_pass:
        print("\n🎉 All acceptance criteria met! Ready for manual inspection.")
        print("\nNext steps:")
        print("  1. Manually inspect sample SAFE and UNSAFE records")
        print("  2. Verify feature distributions make sense")
        print("  3. If approved, generate full 225-scenario dataset")
    else:
        print("\n⚠️  Some acceptance criteria not met. Review and refine.")
    
    return 0 if all_pass else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
