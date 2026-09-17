#!/usr/bin/env python3
"""Generate pilot dataset for inspection and validation."""

from pathlib import Path
import json

from src.veriagent.ml import DatasetGenerator, DatasetValidator
from src.veriagent.ml.dataset_validator import save_scenarios_to_jsonl


def main():
    """Generate pilot dataset."""
    print("=" * 70)
    print("VeriAgent ML Pilot Dataset Generation")
    print("=" * 70)
    
    # Initialize generator with fixed seed
    generator = DatasetGenerator(seed=42)
    print("\n✓ Generator initialized with seed=42")
    
    # Generate pilot scenarios
    pilot_count = 15
    print(f"\n📊 Generating {pilot_count} pilot scenarios...")
    scenarios = generator.generate_pilot(count=pilot_count)
    print(f"✓ Generated {len(scenarios)} scenarios")
    
    # Validate dataset
    print("\n🔍 Validating dataset...")
    validator = DatasetValidator(scenarios)
    is_valid = validator.validate()
    
    print(validator.report())
    
    if not is_valid:
        print("\n❌ Validation failed! Fix errors before proceeding.")
        return 1
    
    # Save to file
    output_path = Path("data/ml/pilot_scenarios.jsonl")
    print(f"\n💾 Saving scenarios to {output_path}...")
    save_scenarios_to_jsonl(scenarios, output_path)
    print(f"✓ Saved {len(scenarios)} scenarios")
    
    # Create manifest
    manifest = {
        "dataset_type": "pilot",
        "total_scenarios": len(scenarios),
        "seed": generator.seed,
        "label_distribution": {
            "SAFE": sum(1 for s in scenarios if s.label.value == "SAFE"),
            "UNSAFE": sum(1 for s in scenarios if s.label.value == "UNSAFE"),
        },
        "scenario_families": list(set(s.scenario_family for s in scenarios)),
        "feature_count": 14,
        "generated_by": "DatasetGenerator v1.0"
    }
    
    manifest_path = Path("data/ml/pilot_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"✓ Saved manifest to {manifest_path}")
    
    # Sample output
    print("\n📋 Sample scenarios:")
    for i, scenario in enumerate(scenarios[:3], 1):
        print(f"\n[{i}] {scenario.scenario_id} ({scenario.label.value})")
        print(f"    Family: {scenario.scenario_family}")
        print(f"    Action: {scenario.action}")
        print(f"    Reason: {scenario.label_reason}")
    
    print("\n" + "=" * 70)
    print("✅ Pilot dataset generation complete!")
    print("=" * 70)
    print(f"\nInspect the pilot at: {output_path}")
    print("If acceptable, proceed to full dataset generation.")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
