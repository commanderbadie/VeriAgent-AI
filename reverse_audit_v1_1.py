"""
Dataset v1.1 Reverse-Reference Audit
====================================

Comprehensive audit of session-scenario relationships.
Identifies missing sessions, orphan sessions, and duplicates.
"""

import json
from pathlib import Path
from collections import Counter
from typing import List, Dict, Set

def load_scenarios(filepath: Path) -> List[Dict]:
    """Load scenarios from JSONL file."""
    scenarios = []
    with open(filepath, 'r') as f:
        for line in f:
            if line.strip():
                scenarios.append(json.loads(line))
    return scenarios

def load_sessions(filepath: Path) -> List[Dict]:
    """Load sessions from JSONL file."""
    sessions = []
    with open(filepath, 'r') as f:
        for line in f:
            if line.strip():
                sessions.append(json.loads(line))
    return sessions

def reverse_audit():
    """Perform comprehensive reverse-reference audit."""
    
    print("=" * 80)
    print("DATASET V1.1 REVERSE-REFERENCE AUDIT")
    print("=" * 80)
    
    data_dir = Path("data/ml/v1_1")
    
    # Load all scenarios
    train = load_scenarios(data_dir / "scenarios_train.jsonl")
    val = load_scenarios(data_dir / "scenarios_validation.jsonl")
    test = load_scenarios(data_dir / "scenarios_test_frozen.jsonl")
    adv = load_scenarios(data_dir / "scenarios_adversarial_frozen.jsonl")
    
    all_scenarios = train + val + test + adv
    
    # Load all sessions
    all_sessions = load_sessions(data_dir / "sessions_full.jsonl")
    
    print(f"\n--- File Counts:")
    print(f"  scenarios_train.jsonl:       {len(train)} scenarios")
    print(f"  scenarios_validation.jsonl:  {len(val)} scenarios")
    print(f"  scenarios_test_frozen.jsonl: {len(test)} scenarios")
    print(f"  scenarios_adversarial_frozen.jsonl: {len(adv)} scenarios")
    print(f"  Total scenarios:             {len(all_scenarios)} scenarios")
    print(f"  sessions_full.jsonl:         {len(all_sessions)} sessions")
    print(f"  Difference:                  {len(all_sessions) - len(all_scenarios)} extra sessions")
    
    # ========================================================================
    # 1. Extract session IDs from scenarios
    # ========================================================================
    
    print(f"\n{'=' * 80}")
    print("1. SCENARIO SESSION REFERENCES")
    print(f"{'=' * 80}")
    
    scenario_session_ids = set(s['session_id'] for s in all_scenarios)
    
    print(f"\nUnique session_ids referenced by scenarios: {len(scenario_session_ids)}")
    
    # Count scenarios per session
    scenario_by_session = {}
    for s in all_scenarios:
        sid = s['session_id']
        if sid not in scenario_by_session:
            scenario_by_session[sid] = []
        scenario_by_session[sid].append(s['scenario_id'])
    
    multi_scenario_sessions = {sid: scenarios for sid, scenarios in scenario_by_session.items() if len(scenarios) > 1}
    
    if multi_scenario_sessions:
        print(f"\n[INFO] Sessions with multiple scenarios: {len(multi_scenario_sessions)}")
        for sid, scenario_ids in list(multi_scenario_sessions.items())[:5]:
            print(f"  {sid}: {len(scenario_ids)} scenarios")
    else:
        print(f"\n[OK] Each session referenced by exactly one scenario")
    
    # ========================================================================
    # 2. Extract session IDs from stored sessions
    # ========================================================================
    
    print(f"\n{'=' * 80}")
    print("2. STORED SESSION RECORDS")
    print(f"{'=' * 80}")
    
    stored_session_ids = [s['session_id'] for s in all_sessions]
    unique_stored_ids = set(stored_session_ids)
    
    print(f"\nTotal session records in sessions_full.jsonl: {len(stored_session_ids)}")
    print(f"Unique session_ids in stored records: {len(unique_stored_ids)}")
    
    # Check for duplicates
    duplicate_count = Counter(stored_session_ids)
    duplicates = {sid: count for sid, count in duplicate_count.items() if count > 1}
    
    if duplicates:
        print(f"\n[FAIL] Duplicate session records detected: {len(duplicates)}")
        for sid, count in list(duplicates.items())[:10]:
            print(f"  {sid}: appears {count} times")
    else:
        print(f"\n[OK] No duplicate session records")
    
    # ========================================================================
    # 3. Missing sessions (referenced but not stored)
    # ========================================================================
    
    print(f"\n{'=' * 80}")
    print("3. MISSING SESSION ANALYSIS")
    print(f"{'=' * 80}")
    
    missing_sessions = scenario_session_ids - unique_stored_ids
    
    print(f"\nScenario session_ids not in stored sessions: {len(missing_sessions)}")
    
    if missing_sessions:
        print(f"\n[FAIL] Missing sessions detected:")
        for sid in sorted(missing_sessions)[:20]:
            scenarios_using = [s['scenario_id'] for s in all_scenarios if s['session_id'] == sid]
            print(f"  {sid}: referenced by {scenarios_using}")
    else:
        print(f"\n[OK] All scenario session_ids have corresponding stored sessions")
    
    # ========================================================================
    # 4. Orphan sessions (stored but not referenced)
    # ========================================================================
    
    print(f"\n{'=' * 80}")
    print("4. ORPHAN SESSION ANALYSIS")
    print(f"{'=' * 80}")
    
    orphan_sessions = unique_stored_ids - scenario_session_ids
    
    print(f"\nStored session_ids not referenced by any scenario: {len(orphan_sessions)}")
    
    if orphan_sessions:
        print(f"\n[WARN] Orphan sessions detected:")
        for sid in sorted(orphan_sessions)[:20]:
            print(f"  {sid}")
        
        # Analyze orphan patterns
        print(f"\nOrphan session patterns:")
        orphan_prefixes = Counter(sid.split('_')[1] if len(sid.split('_')) > 1 else 'unknown' 
                                  for sid in orphan_sessions)
        for prefix, count in orphan_prefixes.most_common():
            print(f"  {prefix}: {count} sessions")
    else:
        print(f"\n[OK] No orphan sessions - all stored sessions are referenced")
    
    # ========================================================================
    # 5. Rules evaluation check
    # ========================================================================
    
    print(f"\n{'=' * 80}")
    print("5. RULES EVALUATION CHECK")
    print(f"{'=' * 80}")
    
    # Check if there's a separate rules file
    rules_file = Path("data/ml/v1_1") / "rules_evaluation.jsonl"
    
    if rules_file.exists():
        rules_scenarios = load_scenarios(rules_file)
        rules_session_ids = set(s['session_id'] for s in rules_scenarios)
        print(f"\nRules evaluation file found: {len(rules_scenarios)} scenarios")
        print(f"Unique rules session_ids: {len(rules_session_ids)}")
        
        # Check if orphans match rules
        orphans_from_rules = orphan_sessions & rules_session_ids
        print(f"Orphan sessions explained by rules: {len(orphans_from_rules)}")
    else:
        print(f"\n[INFO] No separate rules_evaluation.jsonl file found")
        print(f"       Rules scenarios may be mixed with primary dataset")
        rules_session_ids = set()
    
    # ========================================================================
    # 6. Cross-split session verification
    # ========================================================================
    
    print(f"\n{'=' * 80}")
    print("6. CROSS-SPLIT SESSION VERIFICATION")
    print(f"{'=' * 80}")
    
    train_sessions = set(s['session_id'] for s in train)
    val_sessions = set(s['session_id'] for s in val)
    test_sessions = set(s['session_id'] for s in test)
    adv_sessions = set(s['session_id'] for s in adv)
    
    overlaps = [
        ('train', 'validation', train_sessions & val_sessions),
        ('train', 'test', train_sessions & test_sessions),
        ('train', 'adversarial', train_sessions & adv_sessions),
        ('validation', 'test', val_sessions & test_sessions),
        ('validation', 'adversarial', val_sessions & adv_sessions),
        ('test', 'adversarial', test_sessions & adv_sessions),
    ]
    
    print(f"\nCross-split session overlaps:")
    total_overlaps = 0
    for split1, split2, overlap in overlaps:
        status = "[OK]" if len(overlap) == 0 else "[FAIL]"
        print(f"  {status} {split1} ↔ {split2}: {len(overlap)}")
        total_overlaps += len(overlap)
    
    # ========================================================================
    # 7. Summary and recommendations
    # ========================================================================
    
    print(f"\n{'=' * 80}")
    print("SUMMARY AND RECOMMENDATIONS")
    print(f"{'=' * 80}")
    
    print(f"\n--- Counts:")
    print(f"  scenario_count:            {len(all_scenarios)}")
    print(f"  stored_session_count:      {len(stored_session_ids)}")
    print(f"  unique_stored_sessions:    {len(unique_stored_ids)}")
    print(f"  referenced_session_count:  {len(scenario_session_ids)}")
    print(f"  rules_session_count:       {len(rules_session_ids)}")
    print(f"  orphan_session_count:      {len(orphan_sessions)}")
    print(f"  missing_session_count:     {len(missing_sessions)}")
    print(f"  duplicate_session_records: {len(stored_session_ids) - len(unique_stored_ids)}")
    
    print(f"\n--- Validation Status:")
    checks = {
        'missing_session_count = 0': len(missing_sessions) == 0,
        'orphan_session_count = 0': len(orphan_sessions) == 0,
        'duplicate_session_records = 0': len(duplicates) == 0,
        'cross_split_session_overlap = 0': total_overlaps == 0,
    }
    
    for check, passed in checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {check}")
    
    all_passed = all(checks.values())
    
    if all_passed:
        print(f"\n[SUCCESS] All reverse-reference checks passed!")
        print(f"           Dataset v1.1 is ready to commit.")
    else:
        print(f"\n[FAILURE] Some checks failed.")
        print(f"           Review issues above before committing.")
    
    # ========================================================================
    # 8. Recommendations
    # ========================================================================
    
    if orphan_sessions:
        print(f"\n--- Recommended Action:")
        print(f"  Remove {len(orphan_sessions)} orphan sessions from sessions_full.jsonl")
        print(f"  These sessions are not referenced by any scenario and should not be stored.")
        
        print(f"\n  To fix: Regenerate sessions_full.jsonl with only referenced sessions:")
        print(f"    1. Collect all session_ids from scenarios")
        print(f"    2. Filter sessions_full.jsonl to only include those session_ids")
        print(f"    3. Verify orphan_session_count = 0")
    
    if duplicates:
        print(f"\n--- Recommended Action:")
        print(f"  Remove duplicate session records from sessions_full.jsonl")
        print(f"  Each session_id should appear exactly once.")
    
    # Return summary for programmatic use
    return {
        'scenario_count': len(all_scenarios),
        'stored_session_count': len(stored_session_ids),
        'unique_stored_sessions': len(unique_stored_ids),
        'referenced_session_count': len(scenario_session_ids),
        'rules_session_count': len(rules_session_ids),
        'orphan_session_count': len(orphan_sessions),
        'missing_session_count': len(missing_sessions),
        'duplicate_session_records': len(stored_session_ids) - len(unique_stored_ids),
        'cross_split_overlap': total_overlaps,
        'all_passed': all_passed,
        'orphan_session_ids': list(orphan_sessions),
        'referenced_session_ids': list(scenario_session_ids)
    }


if __name__ == "__main__":
    summary = reverse_audit()
    exit(0 if summary['all_passed'] else 1)
