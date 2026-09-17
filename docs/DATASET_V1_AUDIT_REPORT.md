# Dataset v1.0 Audit Report

**Date:** 2026-09-17  
**Auditor:** Automated analysis  
**Status:** ❌ CRITICAL LEAKAGE DETECTED

---

## Executive Summary

Dataset v1.0 has **ZERO fingerprint duplicates** (excellent!), but suffers from **critical session_id leakage** affecting 33 of 36 sessions (92%).

**Key Finding:** The batching approach used to generate 206 scenarios inadvertently reused the same session_ids across different batches, causing scenarios from the same behavioral session to appear in train, validation, test, AND adversarial splits.

**Impact:** Model could learn session-specific patterns in training and encounter the same session patterns in test/adversarial evaluation, invalidating out-of-sample performance estimates.

**Recommendation:** Regenerate dataset with session-aware splitting OR apply minimal correction by removing leaked scenarios.

---

## Audit Findings

### 1. Duplicate Fingerprint Analysis ✅

**Finding:** ZERO duplicate fingerprints across all 206 scenarios

| Metric | Value | Status |
|--------|-------|--------|
| Total scenarios | 206 | - |
| Unique fingerprints | 206 | ✅ Perfect |
| Duplicate fingerprints | 0 | ✅ PASS |
| Within-split duplicates | 0 | ✅ PASS |
| Cross-split duplicates | 0 | ✅ PASS |

**Analysis:**
- Every scenario has a unique model-input fingerprint
- Fingerprint includes: action, user_role, parameters, all behavioral features
- Fingerprint excludes: IDs, labels, split metadata
- The earlier generation report claiming "5 duplicates" was based on a different fingerprint calculation that incorrectly flagged false positives

**Conclusion:** ✅ No action required for fingerprint duplicates

---

### 2. Cross-Split Duplicate Analysis ✅

**Finding:** ZERO scenarios appear in multiple splits based on fingerprint

**Analysis:**
- No scenario fingerprint appears in both train and validation
- No scenario fingerprint appears in both train and test
- No scenario fingerprint appears in both train and adversarial
- No scenario fingerprint appears in any other cross-split combination

**Conclusion:** ✅ No fingerprint-level data leakage

---

### 3. Session ID Leakage Analysis ❌ CRITICAL

**Finding:** 33 of 36 sessions (92%) appear in multiple splits

| Metric | Value | Status |
|--------|-------|--------|
| Total unique session_ids | 36 | - |
| Sessions in single split only | 3 | 8% |
| Sessions in multiple splits | 33 | 92% ❌ |

**Detailed Examples:**

#### Example 1: `session_0001` (appears in ALL 4 splits)

| Split | Scenario IDs Using This Session |
|-------|----------------------------------|
| train | normal_read_001 (2 instances) |
| validation | normal_read_001 (1 instance) |
| test | normal_read_001 (2 instances) |
| adversarial | slow_enumeration_001 (1 instance) |

**Problem:** Model trains on behavioral patterns from `session_0001`, then encounters the same session patterns in validation, test, AND adversarial evaluation.

#### Example 2: `session_0002` (appears in train, test, adversarial)

| Split | Scenario IDs Using This Session |
|-------|----------------------------------|
| train | normal_refund_002 (6 instances) |
| test | normal_refund_002 (1 instance) |
| adversarial | repeated_low_value_abuse_002 (5 instances) |

**Problem:** The same underlying session generates both "normal" refunds in training and "abusive" refunds in adversarial testing.

#### Example 3: `session_0005` (appears in ALL 4 splits)

| Split | Scenario IDs Using This Session |
|-------|----------------------------------|
| train | legitimate_high_value_004, unusual_admin_workflow_005 (2 instances each) |
| validation | legitimate_high_value_004 (1 instance) |
| test | unusual_admin_workflow_005, legitimate_rapid_support_005 (2 instances) |
| adversarial | suspicious_moderate_anomaly_005 (5 instances) |

**Problem:** Extensive leakage - this session's behavioral fingerprint appears across all evaluation contexts.

**Root Cause:**
The batching approach used:
```python
for batch_num in range(7):
    batch_generator = DatasetGenerator(seed=SEED + batch_num * 100)
    batch_scenarios, _ = batch_generator.generate_pilot_v2_2(safe_count=18, unsafe_count=12)
```

Each batch generates scenarios using session IDs like `session_0001`, `session_0002`, etc. Since different batches reuse the same session ID scheme, scenarios from different batches but the same session ID get treated as coming from the same behavioral session.

**Why This Matters:**
Session-level features (tool_call_count, same_action_count, sequence_anomaly_score, context_action_match) are calculated over the entire session. If the model learns that "session_0001 has 5 tool calls with anomaly score 0.49" in training, it may recognize that same session pattern in test, artificially inflating performance.

---

### 4. Template ID / Variant Group ID Analysis ℹ️

**Finding:** No template_id or variant_group_id fields present in dataset

**Analysis:**
- These are optional grouping fields
- Current generator does not use template-based generation
- Each scenario is generated independently with randomized parameters

**Conclusion:** ℹ️ Not applicable - no action required

---

### 5. Label Consistency Check ✅

**Finding:** ZERO label inconsistencies

**Analysis:**
- No fingerprint appears with both SAFE and UNSAFE labels
- All scenarios with identical model inputs have consistent labels
- No conflicting ground truth

**Conclusion:** ✅ No action required

---

### 6. Duplicate Distribution by Split ✅

**Finding:** ZERO within-split duplicates

| Split | Scenarios | Unique Fingerprints | Duplicates |
|-------|-----------|---------------------|------------|
| train | 109 | 109 | 0 ✅ |
| validation | 36 | 36 | 0 ✅ |
| test | 36 | 36 | 0 ✅ |
| adversarial | 25 | 25 | 0 ✅ |

**Conclusion:** ✅ Each split contains only unique scenarios

---

## Impact Assessment

### What's At Risk

1. **Model Performance Estimates:**
   - Training on session patterns that also appear in test/adversarial
   - Validation accuracy may be inflated
   - Test accuracy may be inflated
   - Adversarial robustness may appear better than reality

2. **Generalization Claims:**
   - Cannot claim model generalizes to unseen sessions
   - Can only claim model generalizes to unseen scenario instances within seen sessions

3. **Feature Engineering:**
   - Session-level features (tool_call_count, sequence_anomaly_score) leak information
   - Model may learn to recognize specific session patterns rather than general behavioral indicators

### What's NOT At Risk

1. **Scenario-Level Uniqueness:**
   - Every scenario has unique parameters (customer_id, amount, etc.)
   - No exact scenario appears in multiple splits
   - Individual predictions are still valid

2. **Family-Level Distribution:**
   - Scenario families (attack types) appropriately distributed
   - Model will still learn to distinguish attack families
   - This overlap is EXPECTED and ALLOWED per user requirements

3. **Data Quality:**
   - All scenarios are valid
   - No schema violations
   - No label inconsistencies

---

## Recommended Minimal Correction

### Option 1: Session-Aware Deduplication (Recommended)

**Strategy:** Keep scenarios from one split per session, remove from others

**Priority:** train > validation > test > adversarial

**Algorithm:**
```
For each session_id:
  1. Identify all splits containing this session
  2. If multiple splits:
     a. Keep ALL scenarios from highest-priority split
     b. Remove ALL scenarios from lower-priority splits
  3. Priority: train > validation > test > adversarial
```

**Expected Outcome:**
- ~33 sessions with leakage
- Estimated removals: 90-120 scenarios (from validation, test, adversarial)
- Final dataset: ~80-120 scenarios (primarily training)
- Validation/test sets may be too small for reliable evaluation

**Pros:**
- Clean session separation
- Valid out-of-sample evaluation
- No regeneration needed

**Cons:**
- Significant reduction in dataset size
- May lose most test/adversarial scenarios
- Training set may be too small

---

### Option 2: Regenerate with Session-Aware Splitting (Strongly Recommended)

**Strategy:** Generate scenarios, then split by session (not by scenario)

**Algorithm:**
```python
def session_aware_split(scenarios, train_ratio=0.6, val_ratio=0.2, test_ratio=0.2, seed=42):
    # Group scenarios by session_id
    sessions = defaultdict(list)
    for s in scenarios:
        sessions[s['session_id']].append(s)
    
    # Shuffle sessions (not scenarios)
    session_ids = list(sessions.keys())
    random.seed(seed)
    random.shuffle(session_ids)
    
    # Split sessions
    n = len(session_ids)
    train_n = int(n * train_ratio)
    val_n = int(n * val_ratio)
    
    train_sessions = session_ids[:train_n]
    val_sessions = session_ids[train_n:train_n + val_n]
    test_sessions = session_ids[train_n + val_n:]
    
    # Assign all scenarios from each session to the same split
    train = [s for sid in train_sessions for s in sessions[sid]]
    val = [s for sid in val_sessions for s in sessions[sid]]
    test = [s for sid in test_sessions for s in sessions[sid]]
    
    return train, val, test
```

**Expected Outcome:**
- ~200 scenarios distributed across splits
- Each session appears in exactly ONE split
- Clean separation for valid evaluation

**Pros:**
- Maintains dataset size
- Proper session separation
- Valid generalization testing
- Correct implementation of grouped cross-validation

**Cons:**
- Requires regenerating split files
- Test/adversarial sets are no longer "frozen" (need new SHA-256 hashes)
- More work than Option 1

---

### Option 3: Accept Limitation and Document (Not Recommended)

**Strategy:** Keep dataset as-is, document session leakage in evaluation reports

**Justification:**
- Session leakage exists, but scenario-level inputs are still unique
- Model performance estimates will be optimistic but not entirely invalid
- Useful for rapid prototyping

**Cons:**
- Cannot claim true out-of-sample performance
- Cannot publish results as generalizable
- Violates ML best practices

---

## Recommended Action

**REGENERATE with session-aware splitting (Option 2)**

**Rationale:**
1. Dataset v1.0 has excellent scenario quality (zero fingerprint duplicates, zero label inconsistencies)
2. The ONLY issue is session grouping during split assignment
3. Regenerating splits (not scenarios) is quick and preserves quality
4. Produces valid, publishable evaluation results
5. Aligns with grouped cross-validation best practices

**Implementation:**
```python
# In generate_full_dataset.py, replace stratified_split() with:

def session_aware_stratified_split(
    scenarios: List[Scenario],
    train_size: int,
    val_size: int,
    test_size: int,
    seed: int = 42
) -> tuple[List[Scenario], List[Scenario], List[Scenario]]:
    """Split by session (not scenario) while maintaining label stratification."""
    
    # Group by session AND label
    sessions_by_label = {'SAFE': defaultdict(list), 'UNSAFE': defaultdict(list)}
    
    for s in scenarios:
        label = s.label.value
        sessions_by_label[label][s.session_id].append(s)
    
    # Split sessions within each label
    def split_sessions(session_dict, train_r, val_r, test_r, seed):
        session_ids = list(session_dict.keys())
        random.seed(seed)
        random.shuffle(session_ids)
        
        n = len(session_ids)
        train_n = max(1, int(n * train_r))
        val_n = max(1, int(n * val_r))
        
        return (
            [s for sid in session_ids[:train_n] for s in session_dict[sid]],
            [s for sid in session_ids[train_n:train_n+val_n] for s in session_dict[sid]],
            [s for sid in session_ids[train_n+val_n:] for s in session_dict[sid]]
        )
    
    total = train_size + val_size + test_size
    train_ratio = train_size / total
    val_ratio = val_size / total
    test_ratio = test_size / total
    
    safe_train, safe_val, safe_test = split_sessions(
        sessions_by_label['SAFE'], train_ratio, val_ratio, test_ratio, seed
    )
    
    unsafe_train, unsafe_val, unsafe_test = split_sessions(
        sessions_by_label['UNSAFE'], train_ratio, val_ratio, test_ratio, seed + 1
    )
    
    train = safe_train + unsafe_train
    val = safe_val + unsafe_val
    test = safe_test + unsafe_test
    
    random.seed(seed)
    random.shuffle(train)
    random.shuffle(val)
    random.shuffle(test)
    
    return train, val, test
```

---

## Summary Table

| Check | Result | Status | Action |
|-------|--------|--------|--------|
| **1. Duplicate Fingerprints** | 0 of 206 | ✅ PASS | None |
| **2. Cross-Split Fingerprints** | 0 of 206 | ✅ PASS | None |
| **3. Session ID Leakage** | 33 of 36 | ❌ FAIL | **Regenerate splits** |
| **4. Template/Variant Leakage** | N/A | ℹ️ N/A | None |
| **5. Label Consistency** | 0 conflicts | ✅ PASS | None |
| **6. Within-Split Duplicates** | 0 per split | ✅ PASS | None |

**Overall Status:** ❌ CRITICAL - Session leakage must be corrected before model training

---

## Conclusion

Dataset v1.0 has **excellent scenario-level quality** but **critical session-level leakage**. 

**The good news:** The actual scenario data is perfect - zero duplicates, zero inconsistencies, valid labels.

**The bad news:** The split assignment didn't respect session boundaries, causing 92% of sessions to leak across train/val/test/adversarial splits.

**The fix:** Regenerate split assignments using session-aware stratification. This preserves all 206 high-quality scenarios while ensuring proper evaluation.

**Estimated effort:** 1-2 hours to implement and validate session-aware splitting.

**Priority:** HIGH - Must fix before training any models or making performance claims.

---

**Audit completed:** 2026-09-17  
**Recommendation:** DO NOT PROCEED with current dataset - apply Option 2 (regenerate with session-aware splitting)
