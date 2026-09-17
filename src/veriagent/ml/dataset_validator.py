"""Dataset validation utilities."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .scenario import Scenario, ScenarioLabel


class DatasetValidator:
    """Validates dataset integrity and quality."""
    
    def __init__(self, scenarios: list[Scenario]):
        self.scenarios = scenarios
        self.errors: list[str] = []
        self.warnings: list[str] = []
    
    def validate(self) -> bool:
        """Run all validation checks. Returns True if valid."""
        self.errors.clear()
        self.warnings.clear()
        
        self._check_scenario_validity()
        self._check_unique_ids()
        self._check_no_duplicates()
        self._check_feature_distributions()
        self._check_label_distribution()
        self._check_split_consistency()
        
        return len(self.errors) == 0
    
    def _check_scenario_validity(self) -> None:
        """Validate each scenario individually."""
        for scenario in self.scenarios:
            errors = scenario.validate()
            for error in errors:
                self.errors.append(f"[{scenario.scenario_id}] {error}")
    
    def _check_unique_ids(self) -> None:
        """Ensure all scenario IDs are unique."""
        ids = [s.scenario_id for s in self.scenarios]
        duplicates = [id_ for id_, count in Counter(ids).items() if count > 1]
        if duplicates:
            self.errors.append(f"Duplicate scenario IDs: {duplicates}")
    
    def _check_no_duplicates(self) -> None:
        """Check for near-duplicate scenarios."""
        seen_signatures = set()
        for scenario in self.scenarios:
            # Create signature from key characteristics
            sig = (
                scenario.action,
                scenario.user_role,
                frozenset(scenario.parameters.items()),
                scenario.label
            )
            if sig in seen_signatures:
                self.warnings.append(
                    f"Possible duplicate: {scenario.scenario_id} has same "
                    "action/role/params/label as another scenario"
                )
            seen_signatures.add(sig)
    
    def _check_feature_distributions(self) -> None:
        """Check feature value distributions are reasonable."""
        if not self.scenarios:
            self.errors.append("Empty dataset")
            return
        
        # Check tool_sensitivity values
        valid_sensitivity = {"LOW", "MEDIUM", "HIGH"}
        for scenario in self.scenarios:
            sens = scenario.behavioral_features.tool_sensitivity
            if sens not in valid_sensitivity:
                self.errors.append(
                    f"[{scenario.scenario_id}] Invalid tool_sensitivity: {sens}"
                )
        
        # Check user_role values
        valid_roles = {"ADMIN", "SUPPORT", "GUEST"}
        for scenario in self.scenarios:
            role = scenario.behavioral_features.user_role
            if role not in valid_roles:
                self.errors.append(
                    f"[{scenario.scenario_id}] Invalid user_role: {role}"
                )
        
        # Warn if all amounts are the same (suspiciously uniform)
        amounts = [
            s.behavioral_features.amount_log 
            for s in self.scenarios 
            if s.behavioral_features.amount_log is not None
        ]
        if amounts and len(set(amounts)) == 1:
            self.warnings.append("All amount_log values are identical")
    
    def _check_label_distribution(self) -> None:
        """Check label distribution is reasonable."""
        labels = [s.label for s in self.scenarios]
        counter = Counter(labels)
        
        safe_count = counter.get(ScenarioLabel.SAFE, 0)
        unsafe_count = counter.get(ScenarioLabel.UNSAFE, 0)
        total = len(labels)
        
        if total == 0:
            self.errors.append("No scenarios to validate")
            return
        
        safe_ratio = safe_count / total
        unsafe_ratio = unsafe_count / total
        
        # Warn if severely imbalanced
        if safe_ratio < 0.3 or safe_ratio > 0.9:
            self.warnings.append(
                f"Unusual class balance: {safe_ratio:.1%} SAFE, {unsafe_ratio:.1%} UNSAFE"
            )
    
    def _check_split_consistency(self) -> None:
        """Check splits are properly assigned."""
        valid_splits = {"train", "validation", "test", "adversarial", "pilot"}
        for scenario in self.scenarios:
            if scenario.split not in valid_splits:
                self.errors.append(
                    f"[{scenario.scenario_id}] Invalid split: {scenario.split}"
                )
        
        # Check scenario families don't span multiple splits
        family_splits: dict[str, set[str]] = {}
        for scenario in self.scenarios:
            if scenario.scenario_family not in family_splits:
                family_splits[scenario.scenario_family] = set()
            family_splits[scenario.scenario_family].add(scenario.split)
        
        for family, splits in family_splits.items():
            if len(splits) > 1:
                # Allow pilot to coexist with other splits during testing
                if splits != {"pilot"} and "pilot" in splits:
                    splits_without_pilot = splits - {"pilot"}
                    if len(splits_without_pilot) > 1:
                        self.warnings.append(
                            f"Scenario family '{family}' spans multiple splits: {splits}"
                        )
                elif "pilot" not in splits:
                    self.warnings.append(
                        f"Scenario family '{family}' spans multiple splits: {splits}"
                    )
    
    def report(self) -> str:
        """Generate validation report."""
        lines = ["=" * 70, "Dataset Validation Report", "=" * 70]
        
        lines.append(f"\nTotal scenarios: {len(self.scenarios)}")
        
        # Label distribution
        labels = [s.label for s in self.scenarios]
        counter = Counter(labels)
        lines.append("\nLabel distribution:")
        for label, count in counter.items():
            pct = 100 * count / len(labels) if labels else 0
            lines.append(f"  {label.value}: {count} ({pct:.1f}%)")
        
        # Split distribution
        splits = [s.split for s in self.scenarios]
        split_counter = Counter(splits)
        lines.append("\nSplit distribution:")
        for split, count in split_counter.items():
            pct = 100 * count / len(splits) if splits else 0
            lines.append(f"  {split}: {count} ({pct:.1f}%)")
        
        # Errors
        if self.errors:
            lines.append(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors[:10]:  # Limit output
                lines.append(f"  - {error}")
            if len(self.errors) > 10:
                lines.append(f"  ... and {len(self.errors) - 10} more")
        else:
            lines.append("\n✅ No errors found")
        
        # Warnings
        if self.warnings:
            lines.append(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings[:10]:
                lines.append(f"  - {warning}")
            if len(self.warnings) > 10:
                lines.append(f"  ... and {len(self.warnings) - 10} more")
        
        lines.append("\n" + "=" * 70)
        return "\n".join(lines)


def load_scenarios_from_jsonl(path: Path) -> list[Scenario]:
    """Load scenarios from JSONL file."""
    scenarios = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                scenario = Scenario.from_dict(data)
                scenarios.append(scenario)
            except Exception as e:
                raise ValueError(f"Error parsing line {line_num}: {e}") from e
    return scenarios


def save_scenarios_to_jsonl(scenarios: list[Scenario], path: Path) -> None:
    """Save scenarios to JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for scenario in scenarios:
            json_str = json.dumps(scenario.to_dict(), ensure_ascii=False)
            f.write(json_str + "\n")
