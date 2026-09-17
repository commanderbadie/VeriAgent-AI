# Dataset v1.0 - SUPERSEDED

**Status:** ❌ SUPERSEDED by v1.1  
**Date Deprecated:** 2026-09-17  
**Reason:** Critical session_id leakage (33 of 36 sessions appeared in multiple splits)

---

## Issue Summary

Dataset v1.0 had **zero fingerprint duplicates** (excellent scenario quality) but suffered from **critical session leakage**:
- 33 of 36 sessions (92%) appeared in multiple splits
- Same session patterns appeared in train, validation, test, AND adversarial splits
- Would have invalidated model performance estimates

## Root Cause

Batching approach reused session IDs across batches:
```python
# Batch 1: generated session_0001, session_0002, ...
# Batch 2: generated session_0001, session_0002, ... (SAME IDs!)
# Result: session_0001 scenarios from different batches split across train/val/test
```

## Replacement

**Use Dataset v1.1 instead:**
- Location: `data/ml/v1_1/`
- Fixes: Globally unique session IDs (e.g., `session_batch001_0001`, `session_adv001_0001`)
- Validation: ZERO session leakage, ZERO fingerprint leakage
- Status: ✅ Ready for ML training

## Files Preserved (for reference only)

- `scenarios_train.jsonl` (109 scenarios)
- `scenarios_validation.jsonl` (36 scenarios)
- `scenarios_test_frozen.jsonl` (36 scenarios)
- `scenarios_adversarial_frozen.jsonl` (25 scenarios)
- `sessions_full.jsonl` (3 sessions)
- `full_dataset_manifest.json`

**Do NOT use these files for model training or evaluation.**

---

**Audit Report:** See `docs/DATASET_V1_AUDIT_REPORT.md` for full analysis.
