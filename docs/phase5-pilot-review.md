# Phase 5 Pilot Dataset - Review

**Status:** ✅ Pilot generated and validated  
**Generated:** 2026-09-17  
**Seed:** 42 (deterministic)

---

## Pilot Summary

- **Total scenarios:** 14
- **Label distribution:** 57% SAFE (8), 43% UNSAFE (6)
- **Scenario families:** 6 distinct types
- **Feature count:** 14 behavioral features
- **Validation:** ✅ All checks passed (1 minor warning)
- **Determinism:** ✅ Verified identical across runs

---

## Scenario Families

### SAFE Scenarios (8 total)

1. **simple_read (4 scenarios)**
   - Action: `get_customer`
   - Pattern: Single read operation, LOW sensitivity
   - Features: Low anomaly scores, high context match
   - Example: Get customer 101, tool_call_count=3, sequence_anomaly_score=0.07

2. **normal_refund (4 scenarios)**
   - Action: `refund_customer`
   - Pattern: Small amounts (₹935-₹4,349), has reason, HIGH sensitivity
   - Features: Normal sequences, ~15-40s between actions
   - Example: Refund ₹3,641 for "product defect", amount_log=8.20

### UNSAFE Scenarios (6 total)

3. **large_refund (2 scenarios)**
   - Action: `refund_customer`
   - Pattern: High amounts (₹22,333-₹24,271), exceeds ₹10k threshold
   - Features: amount_log > 10, higher anomaly scores (0.20-0.28)
   - Label reason: Requires human review per policy

4. **missing_params (2 scenarios)**
   - Action: `refund_customer`
   - Pattern: Missing required 'reason' parameter
   - Features: num_parameters=2 (should be 3), higher anomaly (0.34-0.45)
   - Label reason: Policy violation

5. **rapid_sequence (1 scenario)**
   - Action: `refund_customer`
   - Pattern: 8 tool calls, 5 same actions, 2.7s since last
   - Features: is_rapid_sequence=True, sequence_anomaly_score=0.71
   - Label reason: Likely automated abuse

6. **nonexistent_entity (1 scenario)**
   - Action: `get_customer`
   - Pattern: Customer ID 972 (outside normal 101-105 range)
   - Features: 4 retries, 3 failures, anomaly_score=0.78
   - Label reason: Possible enumeration attack

---

## Feature Analysis

### 14 Behavioral Features (No Target Leakage)

**Action characteristics:**
- `tool_sensitivity`: "LOW", "MEDIUM", "HIGH"
- `has_amount`: boolean
- `amount_log`: log(amount) if present
- `num_parameters`: 1-3 in pilot

**Sequence patterns:**
- `tool_call_count`: 1-8 (SAFE avg: 3.1, UNSAFE avg: 4.0)
- `same_action_count`: 1-5 (SAFE avg: 1.0, UNSAFE avg: 2.0)
- `retry_count`: 0-3 (SAFE: 0, UNSAFE avg: 0.7)
- `previous_failure_count`: 0-3 (SAFE: 0, UNSAFE avg: 0.7)

**Temporal patterns:**
- `seconds_since_last_action`: 2.7-48.1s
- `is_rapid_sequence`: True only for rapid_sequence family

**Context signals:**
- `action_frequency`: 1-5
- `sequence_anomaly_score`: 0.05-0.78 (SAFE avg: 0.12, UNSAFE avg: 0.47)
- `context_action_match`: 0.64-0.93 (SAFE avg: 0.85, UNSAFE avg: 0.70)

**User context:**
- `user_role`: All "ADMIN" in pilot (diverse roles in full dataset)

---

## Validation Results

### ✅ Passed Checks

- [x] All scenarios have unique IDs
- [x] No negative counts
- [x] Scores bounded in [0, 1]
- [x] Logical constraints (same_action_count ≤ tool_call_count)
- [x] Amount consistency (has_amount ↔ amount_log)
- [x] Rapid sequence consistency
- [x] No prohibited leakage features
- [x] All labels have justifications
- [x] Split assigned correctly (all "pilot")

### ⚠️ Warnings (1)

- **Possible duplicate:** `simple_read_002` has same action/role/params/label as another scenario
  - **Assessment:** Acceptable for pilot. Both are `get_customer` on customer 105 with ADMIN role.
  - **Mitigation:** Full dataset will have more parameter diversity and customer ID ranges.

---

## Determinism Verification

```python
gen1 = DatasetGenerator(seed=42)
gen2 = DatasetGenerator(seed=42)
scenarios1 = gen1.generate_pilot(15)
scenarios2 = gen2.generate_pilot(15)

assert [s.scenario_id for s in scenarios1] == [s.scenario_id for s in scenarios2]
assert [s.label for s in scenarios1] == [s.label for s in scenarios2]
assert [s.parameters for s in scenarios1] == [s.parameters for s in scenarios2]
```

**Result:** ✅ Identical across runs

---

## Unit Test Results

```
Ran 13 tests in 0.022s

OK

test_deterministic_generation .......................... ok
test_feature_value_ranges .............................. ok
test_label_distribution ................................ ok
test_label_justification ............................... ok
test_no_leakage_features ............................... ok
test_scenario_families ................................. ok
test_scenario_validation ............................... ok
test_unique_scenario_ids ............................... ok
test_jsonl_format ...................................... ok
test_save_and_load_roundtrip ........................... ok
test_duplicate_ids_detected ............................ ok
test_valid_dataset_passes .............................. ok
test_validation_report_generation ...................... ok
```

---

## Key Design Decisions

### 1. Feature Count: 14 (Not 20-25)

**Rationale:** With only 200 total scenarios planned, 20-25 features risks overfitting. Started conservative with 14 meaningful features. Can expand if justified after baseline training.

### 2. No Direct Answer Features

**Prohibited features NOT included:**
- `permission_denied`
- `policy_violated`
- `expected_decision`
- `is_unsafe`
- `should_block`
- `rule_result`

**Reason:** Would let model memorize rules instead of learning behavioral patterns.

### 3. Label Justification Required

Every scenario has `label_reason` explaining why SAFE or UNSAFE. Examples:
- SAFE: "Simple read operation, low sensitivity, normal access pattern"
- UNSAFE: "Rapid sequence of refunds, high action frequency, likely automated abuse"

### 4. Scenario Families for Split Control

Scenarios grouped by family ensures related scenarios stay together during train/val/test split. Prevents data leakage across splits.

### 5. Binary Labels (SAFE/UNSAFE)

All scenarios labeled as SAFE (execute immediately) or UNSAFE (requires review/block). Ambiguous cases labeled UNSAFE (fail-safe).

---

## Observations

### Strengths

1. **Diverse scenario types:** 6 families covering normal operations, policy violations, and attacks
2. **Clear separation:** SAFE vs UNSAFE scenarios differ in multiple features, not just one
3. **Realistic patterns:** Anomaly scores, temporal gaps, retry counts follow expected distributions
4. **No circular labeling:** Features don't directly encode the label

### Potential Improvements for Full Dataset

1. **More user roles:** Currently all ADMIN. Add SUPPORT, GUEST for role-based patterns.
2. **More customer IDs:** Expand beyond 101-105 and 900-999 ranges.
3. **Parameter diversity:** Add more refund reasons, update types.
4. **Temporal diversity:** More variation in session durations and gaps.
5. **Edge cases:** Zero amounts, extremely long sessions, mixed attack patterns.
6. **Adversarial scenarios:** Injection attempts, privilege escalation, parameter tampering.

---

## Acceptance Criteria

| Criterion | Status | Notes |
|-----------|--------|-------|
| 10-20 pilot scenarios | ✅ | 14 scenarios generated |
| No prohibited leakage fields | ✅ | Validated programmatically |
| Labels have justifications | ✅ | All have label_reason |
| Scenario families differ meaningfully | ✅ | 6 distinct patterns |
| Not separated by single variable | ✅ | Multiple feature differences |
| Deterministic (same seed → same output) | ✅ | Verified with two runs |
| All tests pass | ✅ | 13/13 tests pass |

---

## Recommendation

**✅ APPROVED TO PROCEED**

The pilot demonstrates:
- Clean data generation pipeline
- Proper validation safeguards
- No target leakage
- Deterministic behavior
- Meaningful scenario diversity

**Next step:** Generate full dataset with 225 scenarios:
- 120 training
- 40 validation
- 40 test
- 25 adversarial

Expand scenario families to include:
- More user roles (SUPPORT, GUEST)
- Unauthorized access attempts
- Parameter tampering
- Injection patterns
- Update operations
- Mixed attack sequences

---

**Prepared by:** VeriAgent ML Pipeline  
**Review date:** 2026-09-17  
**Reviewer:** Ready for human inspection
