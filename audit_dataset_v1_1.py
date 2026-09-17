"""
Dataset v1.1 Audit Script
=========================

Comprehensive leakage audit for Dataset v1.1.
"""

import json
import hashlib
from pathlib import Path
from collections import defaultdict
from typing import List, Dict

def load_scenarios(filepath: Path) -> List[Dict]:
    """Load scenarios from JSONL file."""
    scenarios = []
    with open(filepath, 'r') as f:
        for line in f:
            scenarios.append(json.loads(line))
    return scenarios

def compute_fingerprint(scenario: Dict) -> str:
    """Compute model-input fingerprint."""
    fp_data = {
        'action': scenario['action'],
        'user_role': scenario['user_role'],
        'parameters': scenario['parameters'],
        'behavioral_features': scenario['behavioral_features']
    }
    fp_json = json.dumps(fp_data, sort_keys=True)
    return hashlib.sha256(fp_json.encode()).hexdigest()

def audit_dataset_v1_1():
    """Perform audit on Dataset v1.1."""
    
    print("=" * 80)
    print("DATASET V1.1 AUDIT REPORT")
    print("=" * 80)
    
    # Load all splits
    data_dir = Path("data/ml/v1_1")
    
    splits = {
        'train': load_scenarios(data_dir / "scenarios_train.jsonl"),
        'validation': load_scenarios(data_dir / "scenarios_validation.jsonl"),
        'test': load_scenarios(data_dir / "scenarios_test_frozen.jsonl"),
        'adversarial': load_scenarios(data_dir / "scenarios_adversarial_frozen.jsonl")
    }
    
    print(f"\nLoaded splits:")
    for split, scenarios in splits.items():
        print(f"  {split:12s}: {len(scenarios):3d} scenarios")
    
    total = sum(len(s) for s in splits.values())
    print(f"  {'Total':12s}: {total:3d} scenarios")
    
    # 1. Session ID Analysis
    print(f"\n{'=' * 80}")
    print("1. SESSION ID LEAKAGE ANALYSIS")
    print(f"{'=' * 80}")
    
    session_map = defaultdict(list)
    
    for split_name, scenarios in splits.items():
        for s in scenarios:
            session_map[s['session_id']].append({
                'split': split_name,
                'scenario_id': s['scenario_id']
            })
    
    session_leakage = {sid: entries for sid, entries in session_map.items() 
                      if len(set(e['split'] for e in entries)) > 1}
    
    print(f"\nTotal unique session_ids: {len(session_map)}")
    print(f"Sessions appearing in multiple splits: {len(session_leakage)}")
    
    if session_leakage:
        print(f"\n[FAIL] Session leakage detected:")
        for sid, entries in sorted(session_leakage.items())[:5]:
            splits_involved = set(e['split'] for e in entries)
            print(f"  {sid}: {splits_involved}")
    else:
        print(f"\n[OK] ZERO session_id leakage")
    
    # 2. Fingerprint Analysis
    print(f"\n{'=' * 80}")
    print("2. FINGERPRINT LEAKAGE ANALYSIS")
    print(f"{'=' * 80}")
    
    fingerprint_map = defaultdict(list)
    
    for split_name, scenarios in splits.items():
        for s in scenarios:
            fp = compute_fingerprint(s)
            fingerprint_map[fp].append({
                'split': split_name,
                'scenario_id': s['scenario_id']
            })
    
    fp_duplicates = {fp: entries for fp, entries in fingerprint_map.items() if len(entries) > 1}
    fp_leakage = {fp: entries for fp, entries in fp_duplicates.items() 
                 if len(set(e['split'] for e in entries)) > 1}
    
    print(f"\nTotal unique fingerprints: {len(fingerprint_map)}")
    print(f"Duplicate fingerprints (any split): {len(fp_duplicates)}")
    print(f"Fingerprints appearing in multiple splits: {len(fp_leakage)}")
    
    if fp_leakage:
        print(f"\n[FAIL] Fingerprint leakage detected:")
        for fp, entries in list(fp_leakage.items())[:5]:
            splits_involved = set(e['split'] for e in entries)
            print(f"  {fp[:16]}...: {splits_involved}")
    else:
        print(f"\n[OK] ZERO fingerprint leakage")
    
    # 3. Cross-Split Analysis
    print(f"\n{'=' * 80}")
    print("3. PAIRWISE CROSS-SPLIT ANALYSIS")
    print(f"{'=' * 80}")
    
    train_sessions = set(s['session_id'] for s in splits['train'])
    val_sessions = set(s['session_id'] for s in splits['validation'])
    test_sessions = set(s['session_id'] for s in splits['test'])
    adv_sessions = set(s['session_id'] for s in splits['adversarial'])
    
    train_fps = set(compute_fingerprint(s) for s in splits['train'])
    val_fps = set(compute_fingerprint(s) for s in splits['validation'])
    test_fps = set(compute_fingerprint(s) for s in splits['test'])
    adv_fps = set(compute_fingerprint(s) for s in splits['adversarial'])
    
    pairs = [
        ('train', 'validation', train_sessions, val_sessions, train_fps, val_fps),
        ('train', 'test', train_sessions, test_sessions, train_fps, test_fps),
        ('train', 'adversarial', train_sessions, adv_sessions, train_fps, adv_fps),
        ('validation', 'test', val_sessions, test_sessions, val_fps, test_fps),
        ('validation', 'adversarial', val_sessions, adv_sessions, val_fps, adv_fps),
        ('test', 'adversarial', test_sessions, adv_sessions, test_fps, adv_fps),
    ]
    
    print(f"\nSession ID overlaps:")
    all_session_overlaps_zero = True
    for split1, split2, sess1, sess2, _, _ in pairs:
        overlap = len(sess1 & sess2)
        status = "[OK]" if overlap == 0 else "[FAIL]"
        print(f"  {status} {split1:12s} <-> {split2:12s}: {overlap}")
        if overlap > 0:
            all_session_overlaps_zero = False
    
    print(f"\nFingerprint overlaps:")
    all_fp_overlaps_zero = True
    for split1, split2, _, _, fps1, fps2 in pairs:
        overlap = len(fps1 & fps2)
        status = "[OK]" if overlap == 0 else "[FAIL]"
        print(f"  {status} {split1:12s} <-> {split2:12s}: {overlap}")
        if overlap > 0:
            all_fp_overlaps_zero = False
    
    # 4. Label Distribution
    print(f"\n{'=' * 80}")
    print("4. LABEL DISTRIBUTION")
    print(f"{'=' * 80}")
    
    for split_name, scenarios in splits.items():
        safe = sum(1 for s in scenarios if s['label'] == 'SAFE')
        unsafe = sum(1 for s in scenarios if s['label'] == 'UNSAFE')
        print(f"\n{split_name:12s}: {len(scenarios)} total")
        print(f"  SAFE:   {safe:3d} ({100*safe/len(scenarios):.1f}%)")
        print(f"  UNSAFE: {unsafe:3d} ({100*unsafe/len(scenarios):.1f}%)")
    
    # 5. Final Summary
    print(f"\n{'=' * 80}")
    print("FINAL SUMMARY")
    print(f"{'=' * 80}")
    
    print(f"\nCritical Checks:")
    print(f"  Session leakage:     {'PASS' if len(session_leakage) == 0 else 'FAIL'} "
          f"({len(session_leakage)} leaks)")
    print(f"  Fingerprint leakage: {'PASS' if len(fp_leakage) == 0 else 'FAIL'} "
          f"({len(fp_leakage)} leaks)")
    print(f"  All pairwise checks: {'PASS' if all_session_overlaps_zero and all_fp_overlaps_zero else 'FAIL'}")
    
    if len(session_leakage) == 0 and len(fp_leakage) == 0:
        print(f"\n[SUCCESS] Dataset v1.1 passes all leakage checks!")
        print(f"           Ready for ML model training.")
        return 0
    else:
        print(f"\n[FAILURE] Dataset v1.1 has leakage issues.")
        print(f"           Do not use for training.")
        return 1


if __name__ == "__main__":
    exit(audit_dataset_v1_1())
