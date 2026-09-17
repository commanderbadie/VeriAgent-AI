"""Manual review script for Pilot v2.2."""
import json
import math
from pathlib import Path
from collections import Counter

# Load scenarios
scenarios = []
with open('data/ml/pilot_v2_2_scenarios.jsonl', 'r') as f:
    for line in f:
        scenarios.append(json.loads(line))

# Load sessions
sessions = []
with open('data/ml/pilot_v2_2_sessions.jsonl', 'r') as f:
    for line in f:
        sessions.append(json.loads(line))

print('=' * 70)
print('PILOT V2.2 MANUAL REVIEW')
print('=' * 70)

print(f'\nTotal scenarios: {len(scenarios)}')
print(f'Total sessions: {len(sessions)}')

# INTEGRITY CHECKS
print('\n' + '=' * 70)
print('INTEGRITY CHECKS')
print('=' * 70)

# Check 1: No _padding_id
has_padding = [s for s in scenarios if '_padding_id' in s['parameters']]
status = '✅ PASS' if not has_padding else f'❌ FAIL - Found {len(has_padding)}'
print(f'\n1. No _padding_id in parameters: {status}')

# Check 2: Valid roles
invalid_roles = [s for s in scenarios if s['user_role'] not in ['ADMIN', 'AGENT', 'READ_ONLY']]
status = '✅ PASS' if not invalid_roles else f'❌ FAIL - Found {len(invalid_roles)}'
print(f'2. Valid VeriAgent roles: {status}')

# Check 3: Valid entities for SAFE
safe_scenarios = [s for s in scenarios if s['label'] == 'SAFE']
safe_with_invalid_ids = []
for s in safe_scenarios:
    if 'customer_id' in s['parameters']:
        cid = s['parameters']['customer_id']
        if not (101 <= cid <= 120):
            safe_with_invalid_ids.append(s['scenario_id'])
status = '✅ PASS' if not safe_with_invalid_ids else f'❌ FAIL - Found {len(safe_with_invalid_ids)}'
print(f'3. SAFE uses valid entities (101-120): {status}')

# Check 4: amount_log consistency
amount_mismatches = []
for s in scenarios:
    if s['behavioral_features']['has_amount']:
        if 'amount' in s['parameters']:
            expected = math.log(max(1.0, s['parameters']['amount']))
            actual = s['behavioral_features']['amount_log']
            if abs(expected - actual) > 0.01:
                amount_mismatches.append(s['scenario_id'])
status = '✅ PASS' if not amount_mismatches else f'❌ FAIL - Found {len(amount_mismatches)}'
print(f'4. amount_log matches final amount: {status}')

# Check 5: target_event_index exists
missing_index = [s for s in scenarios if 'target_event_index' not in s]
status = '✅ PASS' if not missing_index else f'❌ FAIL - Missing {len(missing_index)}'
print(f'5. target_event_index present: {status}')

# Check 6: Exact quotas
safe_count = len([s for s in scenarios if s['label'] == 'SAFE'])
unsafe_count = len([s for s in scenarios if s['label'] == 'UNSAFE'])
status = '✅ PASS' if safe_count == 18 and unsafe_count == 12 else f'❌ FAIL - Got {safe_count}/{unsafe_count}'
print(f'6. Exact quotas (18 SAFE / 12 UNSAFE): {status}')

# Check 7: Session reproducibility
sessions_by_id = {s['session_id']: s for s in sessions}
missing_sessions = [sc for sc in scenarios if sc['session_id'] not in sessions_by_id]
status = '✅ PASS' if not missing_sessions else f'❌ FAIL - {len(missing_sessions)} scenarios missing sessions'
print(f'7. All sessions present: {status}')

# COUNTEREXAMPLE ANALYSIS
print('\n' + '=' * 70)
print('COUNTEREXAMPLE ANALYSIS')
print('=' * 70)

families = {}
for s in scenarios:
    fam = s['scenario_family']
    label = s['label']
    if fam not in families:
        families[fam] = {'SAFE': 0, 'UNSAFE': 0, 'examples': []}
    families[fam][label] += 1
    families[fam]['examples'].append(s['scenario_id'])

print(f'\nTotal scenario families: {len(families)}')

# Rapid patterns counterexample
rapid_safe = [s for s in safe_scenarios if s['behavioral_features']['is_rapid_sequence']]
rapid_unsafe = [s for s in scenarios if s['label'] == 'UNSAFE' and s['behavioral_features']['is_rapid_sequence']]
print(f'\nRapid sequence counterexamples:')
print(f'  SAFE with rapid=True: {len(rapid_safe)}')
print(f'  UNSAFE with rapid=True: {len(rapid_unsafe)}')
status = '✅ GOOD' if rapid_safe else '⚠️ No SAFE rapid examples'
print(f'  Status: {status}')

# FEATURE DISTRIBUTIONS
print('\n' + '=' * 70)
print('FEATURE DISTRIBUTIONS')
print('=' * 70)

safe_anomalies = [s['behavioral_features']['sequence_anomaly_score'] for s in safe_scenarios]
unsafe_anomalies = [s['behavioral_features']['sequence_anomaly_score'] for s in scenarios if s['label'] == 'UNSAFE']

print(f'\nAnomaly Scores:')
print(f'  SAFE:   avg={sum(safe_anomalies)/len(safe_anomalies):.3f}, '
      f'min={min(safe_anomalies):.3f}, max={max(safe_anomalies):.3f}')
print(f'  UNSAFE: avg={sum(unsafe_anomalies)/len(unsafe_anomalies):.3f}, '
      f'min={min(unsafe_anomalies):.3f}, max={max(unsafe_anomalies):.3f}')

overlap = max(safe_anomalies) > min(unsafe_anomalies)
print(f'  Overlap: {"✅ YES (as designed)" if overlap else "⚠️ NO"}')

# SAMPLE INSPECTION
print('\n' + '=' * 70)
print('SAMPLE SCENARIO INSPECTION')
print('=' * 70)

print('\n--- SAFE Sample ---')
safe_sample = safe_scenarios[0]
print(f'ID: {safe_sample["scenario_id"]}')
print(f'Family: {safe_sample["scenario_family"]}')
print(f'Action: {safe_sample["action"]} by {safe_sample["user_role"]}')
print(f'Reason: {safe_sample["label_reason"]}')
print(f'Parameters: {safe_sample["parameters"]}')
print(f'Anomaly: {safe_sample["behavioral_features"]["sequence_anomaly_score"]:.3f}')

print('\n--- UNSAFE Sample ---')
unsafe_sample = [s for s in scenarios if s['label'] == 'UNSAFE'][0]
print(f'ID: {unsafe_sample["scenario_id"]}')
print(f'Family: {unsafe_sample["scenario_family"]}')
print(f'Action: {unsafe_sample["action"]} by {unsafe_sample["user_role"]}')
print(f'Reason: {unsafe_sample["label_reason"]}')
print(f'Parameters: {unsafe_sample["parameters"]}')
print(f'Anomaly: {unsafe_sample["behavioral_features"]["sequence_anomaly_score"]:.3f}')

# FINAL VERDICT
print('\n' + '=' * 70)
print('FINAL VERDICT')
print('=' * 70)

all_checks = [
    not has_padding,
    not invalid_roles,
    not safe_with_invalid_ids,
    not amount_mismatches,
    not missing_index,
    safe_count == 18 and unsafe_count == 12,
    not missing_sessions,
]

if all(all_checks):
    print('\n✅ ALL CHECKS PASSED - Pilot v2.2 is ready for use!')
    print('   Proceed to full dataset generation (225 scenarios).')
else:
    print('\n⚠️ SOME CHECKS FAILED - Review issues above before proceeding.')

print('\n' + '=' * 70)
