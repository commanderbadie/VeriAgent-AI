# Dataset v1.1 - Final Audit Complete ✅

**Date:** 2026-09-17  
**Status:** FROZEN AND VALIDATED  
**Git Tag:** `phase5-dataset-v1.1-frozen`  
**Git Commit:** `76cb94c`

---

## Audit Summary

Dataset v1.1 has passed **all validation checks** and is ready for ML model training.

### Final Counts

| Metric | Count | Validation |
|--------|-------|------------|
| **scenario_count** | 235 | ✅ |
| **stored_session_count** | 235 | ✅ |
| **referenced_session_count** | 235 | ✅ |
| **rules_session_count** | 0 | ✅ |
| **orphan_session_count** | 0 | ✅ REQUIRED |
| **missing_session_count** | 0 | ✅ REQUIRED |
| **duplicate_session_records** | 0 | ✅ REQUIRED |

### Split Distribution

| Split | Scenarios | Sessions | SAFE | UNSAFE |
|-------|-----------|----------|------|--------|
| Train | 125 | 125 | 75 (60%) | 50 (40%) |
| Validation | 41 | 41 | 25 (61%) | 16 (39%) |
| Test (FROZEN) | 44 | 44 | 26 (59%) | 18 (41%) |
| Adversarial (FROZEN) | 25 | 25 | 0 (0%) | 25 (100%) |
| **Total** | **235** | **235** | **126** | **109** |

---

## Validation Checks (All Passed)

### 1. Session-Scenario Mapping ✅

- [x] Every scenario references exactly one session
- [x] Every session is referenced by exactly one scenario
- [x] No missing sessions (scenario references non-existent session)
- [x] No orphan sessions (session not referenced by any scenario)
- [x] No duplicate session records

**Result:** Perfect 1:1 mapping between scenarios and sessions.

### 2. Cross-Split Leakage ✅

**Session ID Leakage:**
- [x] train ↔ validation: 0
- [x] train ↔ test: 0
- [x] train ↔ adversarial: 0
- [x] validation ↔ test: 0
- [x] validation ↔ adversarial: 0
- [x] test ↔ adversarial: 0

**Fingerprint Leakage:**
- [x] train ↔ validation: 0
- [x] train ↔ test: 0
- [x] train ↔ adversarial: 0
- [x] validation ↔ test: 0
- [x] validation ↔ adversarial: 0
- [x] test ↔ adversarial: 0

**Result:** Zero leakage across all splits.

### 3. Data Quality ✅

- [x] All scenarios have valid actions
- [x] All scenarios conform to ActionSchemaRegistry
- [x] All behavioral features present and valid
- [x] No `_padding_id` or artificial parameters
- [x] All labels have justification reasons
- [x] SAFE scenarios use valid database entities (101-120)

### 4. Test Suite ✅

- [x] All 165 tests passing (1 skipped - Ollama integration)
- [x] No regressions in existing functionality
- [x] Dataset generation tests pass
- [x] Integrity tests pass

---

## Issues Found and Fixed

### Issue 1: Orphan Sessions (FIXED)

**Problem:** 246 sessions stored, but only 235 referenced by scenarios

**Root Cause:** Adversarial generation created 36 scenarios but only selected top 25. The 11 rejected scenarios' sessions were still stored.

**Sessions Affected:**
- `session_adv001_0003`, `session_adv001_0004`, `session_adv001_0011`
- `session_adv002_0003`, `session_adv002_0007`, `session_adv002_0011`, `session_adv002_0012`
- `session_adv003_0003`, `session_adv003_0007`, `session_adv003_0011`, `session_adv003_0012`

**Fix Applied:**
1. Identified all session_ids referenced by scenarios (235 unique)
2. Filtered `sessions_full.jsonl` to only include referenced sessions
3. Created backup of original file (`sessions_full.jsonl.backup`)
4. Verified orphan_session_count = 0

**Verification:**
```
Before: 246 sessions (235 referenced + 11 orphans)
After:  235 sessions (235 referenced + 0 orphans) ✅
```

---

## Audit Scripts

Three audit scripts were created and all pass:

### 1. `audit_dataset_v1_1.py`
**Purpose:** Check cross-split session and fingerprint leakage  
**Exit Code:** 0 (PASS)  
**Key Checks:**
- Session ID overlap across all split pairs
- Fingerprint overlap across all split pairs
- Label distribution
- Overall integrity

### 2. `reverse_audit_v1_1.py`
**Purpose:** Verify session-scenario reference integrity  
**Exit Code:** 0 (PASS)  
**Key Checks:**
- Missing sessions (referenced but not stored)
- Orphan sessions (stored but not referenced)
- Duplicate session records
- Rules evaluation session tracking

### 3. `fix_orphan_sessions.py`
**Purpose:** Remove orphan sessions from storage  
**Exit Code:** 0 (SUCCESS)  
**Actions:**
- Backed up original `sessions_full.jsonl`
- Filtered to only referenced sessions
- Verified final counts

---

## Files Committed

### Dataset Files (data/ml/v1_1/)
1. `scenarios_train.jsonl` - 125 training scenarios
2. `scenarios_validation.jsonl` - 41 validation scenarios
3. `scenarios_test_frozen.jsonl` - 44 test scenarios (FROZEN)
4. `scenarios_adversarial_frozen.jsonl` - 25 adversarial scenarios (FROZEN)
5. `sessions_full.jsonl` - 235 session records
6. `sessions_full.jsonl.backup` - Original with 246 sessions (reference)
7. `full_dataset_manifest.json` - Complete metadata with SHA-256 hashes

### Documentation
1. `docs/DATASET_V1_1_FINAL_REPORT.md` - Complete technical report
2. `docs/DATASET_V1_AUDIT_REPORT.md` - v1.0 audit showing original issues
3. `docs/DATASET_V1_1_AUDIT_COMPLETE.md` - This file
4. `data/ml/v1_0_SUPERSEDED.md` - v1.0 deprecation notice

### Scripts
1. `generate_dataset_v1_1.py` - Generation script with session-aware splitting
2. `audit_dataset_v1_1.py` - Leakage audit script
3. `reverse_audit_v1_1.py` - Session-scenario reference audit
4. `fix_orphan_sessions.py` - Orphan removal script

---

## Manifest Updates

The `full_dataset_manifest.json` now includes:

```json
{
  "totals": {
    "total_scenarios": 235,
    "unique_sessions": 235,
    "stored_session_count": 235,
    "referenced_session_count": 235,
    "orphan_session_count": 0,
    "missing_session_count": 0,
    "rules_session_count": 0
  },
  
  "leakage_audit": {
    "session_overlap": {
      "train_val": 0,
      "train_test": 0,
      "train_adv": 0,
      "val_test": 0,
      "val_adv": 0,
      "test_adv": 0,
      "status": "PASS"
    },
    "fingerprint_overlap": {
      "train_val": 0,
      "train_test": 0,
      "train_adv": 0,
      "val_test": 0,
      "val_adv": 0,
      "test_adv": 0,
      "status": "PASS"
    },
    "session_references": {
      "missing_sessions": 0,
      "orphan_sessions": 0,
      "status": "PASS"
    }
  }
}
```

---

## Comparison: v1.0 vs v1.1

| Metric | v1.0 | v1.1 | Status |
|--------|------|------|--------|
| Total scenarios | 206 | 235 | +29 ✅ |
| Session leakage | 33 (92%) | 0 (0%) | **FIXED** ✅ |
| Fingerprint duplicates | 0 | 0 | Maintained ✅ |
| Orphan sessions | N/A | 0 | New check ✅ |
| Missing sessions | N/A | 0 | New check ✅ |
| Train size | 109 | 125 | +16 ✅ |
| Val size | 36 | 41 | +5 ✅ |
| Test size | 36 | 44 | +8 ✅ |
| All tests passing | Yes | Yes | Maintained ✅ |

---

## SHA-256 Hashes

All dataset files have been hashed and recorded in the manifest:

- `scenarios_train.jsonl`: Recorded ✅
- `scenarios_validation.jsonl`: Recorded ✅
- `scenarios_test_frozen.jsonl`: Recorded ✅ (FROZEN)
- `scenarios_adversarial_frozen.jsonl`: Recorded ✅ (FROZEN)
- `sessions_full.jsonl`: Recorded ✅
- `full_dataset_manifest.json`: Self-describing ✅

Any modification to frozen files will be detectable via hash mismatch.

---

## Usage Guidelines

### For ML Training (Approved)

**Use:**
- `scenarios_train.jsonl` (125 scenarios) - for model training
- `scenarios_validation.jsonl` (41 scenarios) - for hyperparameter tuning

**Do NOT Use Yet:**
- `scenarios_test_frozen.jsonl` - reserved for final evaluation
- `scenarios_adversarial_frozen.jsonl` - reserved for robustness testing

### For Feature Extraction

All scenarios contain pre-computed behavioral features:
```json
{
  "behavioral_features": {
    "tool_sensitivity": "HIGH",
    "has_amount": true,
    "amount_log": 8.517,
    "num_parameters": 3,
    "tool_call_count": 4,
    "same_action_count": 1,
    "retry_count": 0,
    "previous_failure_count": 0,
    "seconds_since_last_action": 45.578,
    "is_rapid_sequence": false,
    "action_frequency": 1,
    "sequence_anomaly_score": 0.106,
    "context_action_match": 0.923,
    "user_role": "ADMIN"
  }
}
```

**Next Step:** Convert these features to numeric arrays for sklearn models.

---

## Final Verification Commands

To reproduce the validation:

```bash
# Run test suite
py -m unittest discover -s tests -p "test_*.py"
# Expected: 165 tests, 0 failures, 1 skipped

# Run leakage audit
py audit_dataset_v1_1.py
# Expected: exit code 0, all checks PASS

# Run reverse-reference audit
py reverse_audit_v1_1.py
# Expected: exit code 0, all checks PASS
```

---

## Conclusion

**Dataset v1.1 Status:** ✅ FROZEN AND VALIDATED

**Quality:** EXCELLENT
- Zero session leakage
- Zero fingerprint leakage
- Zero orphan sessions
- Zero missing sessions
- Perfect 1:1 scenario-session mapping

**Quantity:** ADEQUATE
- 235 total scenarios
- 125 training (sufficient for baseline models)
- 41 validation (sufficient for hyperparameter tuning)
- 69 held-out (44 test + 25 adversarial)

**Recommendation:** **APPROVED FOR ML MODEL TRAINING**

---

**Audit Completed:** 2026-09-17  
**Audited By:** Automated validation + manual review  
**Status:** READY FOR PRODUCTION USE  
**Next Phase:** Feature extraction and baseline model training  
**Awaiting:** User approval to proceed
