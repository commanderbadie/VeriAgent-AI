"""
Fix orphan sessions in Dataset v1.1
====================================

Remove orphan sessions from sessions_full.jsonl.
Keep only sessions referenced by actual scenarios.
"""

import json
from pathlib import Path

def fix_orphan_sessions():
    """Remove orphan sessions and regenerate sessions_full.jsonl."""
    
    print("=" * 80)
    print("FIXING ORPHAN SESSIONS IN DATASET V1.1")
    print("=" * 80)
    
    data_dir = Path("data/ml/v1_1")
    
    # Load all scenarios
    print("\nLoading scenarios...")
    all_scenarios = []
    
    for filename in ['scenarios_train.jsonl', 'scenarios_validation.jsonl', 
                     'scenarios_test_frozen.jsonl', 'scenarios_adversarial_frozen.jsonl']:
        filepath = data_dir / filename
        with open(filepath, 'r') as f:
            for line in f:
                if line.strip():
                    all_scenarios.append(json.loads(line))
    
    print(f"  Loaded {len(all_scenarios)} scenarios")
    
    # Collect all referenced session_ids
    referenced_session_ids = set(s['session_id'] for s in all_scenarios)
    print(f"  Unique referenced session_ids: {len(referenced_session_ids)}")
    
    # Load existing sessions
    print("\nLoading existing sessions...")
    sessions_file = data_dir / "sessions_full.jsonl"
    
    all_sessions = []
    with open(sessions_file, 'r') as f:
        for line in f:
            if line.strip():
                all_sessions.append(json.loads(line))
    
    print(f"  Loaded {len(all_sessions)} sessions")
    
    # Filter to only referenced sessions
    filtered_sessions = [s for s in all_sessions if s['session_id'] in referenced_session_ids]
    
    orphan_count = len(all_sessions) - len(filtered_sessions)
    
    print(f"\n  Filtered sessions: {len(filtered_sessions)}")
    print(f"  Removed orphans: {orphan_count}")
    
    if orphan_count > 0:
        # Backup original
        backup_file = data_dir / "sessions_full.jsonl.backup"
        print(f"\n  Creating backup: {backup_file}")
        sessions_file.rename(backup_file)
        
        # Write filtered sessions
        print(f"  Writing filtered sessions to {sessions_file}")
        with open(sessions_file, 'w') as f:
            for session in filtered_sessions:
                f.write(json.dumps(session) + '\n')
        
        print(f"\n[SUCCESS] Removed {orphan_count} orphan sessions")
        print(f"          sessions_full.jsonl now has {len(filtered_sessions)} sessions")
        print(f"          Backup saved to sessions_full.jsonl.backup")
    else:
        print(f"\n[OK] No orphan sessions found - no changes needed")
    
    # Verify
    print(f"\n{'=' * 80}")
    print("VERIFICATION")
    print(f"{'=' * 80}")
    
    # Reload and verify
    with open(sessions_file, 'r') as f:
        verified_sessions = [json.loads(line) for line in f if line.strip()]
    
    verified_session_ids = set(s['session_id'] for s in verified_sessions)
    
    missing = referenced_session_ids - verified_session_ids
    orphans = verified_session_ids - referenced_session_ids
    
    print(f"\n  Scenarios: {len(all_scenarios)}")
    print(f"  Sessions: {len(verified_sessions)}")
    print(f"  Referenced session_ids: {len(referenced_session_ids)}")
    print(f"  Stored session_ids: {len(verified_session_ids)}")
    print(f"  Missing sessions: {len(missing)}")
    print(f"  Orphan sessions: {len(orphans)}")
    
    if len(missing) == 0 and len(orphans) == 0:
        print(f"\n[SUCCESS] All checks passed!")
        print(f"          Every scenario has exactly one session.")
        print(f"          Every session is referenced by exactly one scenario.")
        return True
    else:
        print(f"\n[FAILURE] Issues remain:")
        if missing:
            print(f"          {len(missing)} sessions missing from storage")
        if orphans:
            print(f"          {len(orphans)} orphan sessions still present")
        return False


if __name__ == "__main__":
    success = fix_orphan_sessions()
    exit(0 if success else 1)
