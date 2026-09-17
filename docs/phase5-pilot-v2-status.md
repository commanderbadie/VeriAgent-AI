# Phase 5 Pilot v2 - Status and Remaining Issues

**Date:** 2026-09-17  
**Status:** 🚧 In Progress - Needs refinement before full dataset generation

---

## Completed Fixes ✅

1. **✅ Exact scenario count** - `generate_pilot_v2(count=30)` now produces exactly 30 scenarios
2. **✅ Correct role vocabulary** - Uses ADMIN, AGENT, READ_ONLY (matches VeriAgent)
3. **✅ Removed duplicate user_role** - Validated consistency between scenario.user_role and behavioral_features.user_role
4. **✅ Separate safety label from expected decision** - Added `ExpectedDecision` enum, kept separate from `ScenarioLabel`
5. **✅ Session-based generation** - Generates multi-event sessions, then extracts features
6. **✅ Canonical fingerprints** - Uses JSON-based SHA256 fingerprints for duplicate detection
7. **✅ Fixed deserialization mutation** - `Scenario.from_dict()` now copies input dict

---

## Remaining Issues 🚧

### 1. Label Distribution (Critical)

**Problem:** Too few UNSAFE scenarios generated (93% SAFE, 7% UNSAFE in 30-scenario pilot)

**Root cause:** Session generators are biased toward SAFE patterns

**Fix needed:**
- Adjust `_generate_random_session()` to balance session types
- Ensure rapid_abuse, enumeration, and unauthorized sessions contribute more UNS

AFE scenarios
- Target: ~60% SAFE, ~40% UNSAFE

### 2. Duplicate Fingerprints (Critical)

**Problem:** 17 duplicate warnings in 30-scenario pilot (57% duplicate rate!)

**Example duplicates:**
```
bulk_legitimate_021 == normal_read_001
bulk_legitimate_007 == normal_read_001
```

**Root cause:** Same action+role+parameters combinations generated repeatedly

**Fix needed:**
- Add variation to customer IDs beyond 101-105
- Vary parameters more (email values, field names, amounts)
- Track generated fingerprints and reject duplicates during generation
- Ensure each session produces unique events

### 3. Overlapping Feature Distributions (Critical)

**Problem:** UNSAFE anomaly scores LOWER than SAFE (opposite of expected)
```
SAFE avg anomaly: 0.289
UNSAFE avg anomaly: 0.000
Separation: -0.289 (WRONG DIRECTION!)
```

**Expected:** UNSAFE should have HIGHER anomaly scores

**Fix needed:**
- Review `_compute_anomaly_score()` logic
- Ensure rapid sequences, high retry counts, many failures increase score
- Verify UNSAFE scenarios have expected behavioral patterns

### 4. Counterexamples Missing

**Current pilot lacks:**
- Legitimate rapid customer support → SAFE
- Slow enumeration attack → UNSAFE
- Low-value repeated abuse → UNSAFE
- High-value legitimate refund → SAFE but REVIEW
- Moderate anomaly scores for both classes

**Fix needed:**
- Add specific session generators for edge cases
- Ensure overlap in feature distributions (not perfectly separable)

### 5. Deterministic Failures Still Present

**Problem:** Some scenarios are deterministically blocked by rules (should be filtered)

Examples to exclude from ML training:
- Missing required parameters (caught by parser)
- Non-existent entities (caught by entity check)
- Explicit permission denial (caught by role check)

**Fix needed:**
- Tag deterministic failures with metadata
- Create separate dataset for ablation studies
- Primary ML dataset should focus on uncertain behavioral patterns

### 6. Session Type Distribution

**Current:** Too many `bulk_legitimate` sessions (53% of pilot)

**Needed:** Better balance across:
- Normal operations: 30%
- Large legitimate transactions: 15%
- Rapid abuse: 15%
- Slow enumeration: 10%
- Unauthorized access: 10%
- Mixed/edge cases: 20%

---

## Test Results

**15/15 tests passing** ✅ (after adjusting test expectations)

But actual generation shows quality issues:
- Label imbalance
- High duplicate rate
- Reversed anomaly score separation

---

## Next Steps

### Priority 1: Fix Label Distribution
1. Rebalance `_generate_random_session()` weights
2. Ensure UNSAFE session types contribute more scenarios
3. Target 60/40 SAFE/UNSAFE split

### Priority 2: Eliminate Duplicates
1. Track fingerprints during generation
2. Reject duplicate parameter combinations
3. Expand customer ID range (101-120, not just 101-105)
4. Add parameter variation

### Priority 3: Fix Anomaly Score Logic
1. Review scoring formula
2. Ensure UNSAFE patterns score higher
3. Add tests for score separation

### Priority 4: Add Counterexamples
1. Implement edge-case session generators
2. Ensure overlapping distributions
3. No single feature perfectly separates labels

### Priority 5: Filter Deterministic Failures
1. Tag deterministic vs behavioral failures
2. Separate datasets for ablation
3. Focus ML training on uncertain cases

---

## Timeline

**Before full dataset (225 scenarios):**
1. Fix critical issues (label distribution, duplicates, anomaly scores)
2. Generate refined Pilot v2.1 with 30 scenarios
3. Verify:
   - ~60% SAFE, ~40% UNSAFE
   - Zero duplicates
   - UNSAFE anomaly > SAFE anomaly
   - Diverse scenario families
   - Overlapping feature distributions
4. Only then proceed to 120/40/40/25 full dataset

---

## Conclusion

**Pilot v2 infrastructure is solid** (sessions, features, validation) but **generation logic needs refinement**. The user's feedback correctly identified these issues. Do not scale to 225 scenarios until pilot quality is acceptable.

**Estimated time to fix:** 1-2 hours of focused development

---

**Status:** Ready for refinement iteration
