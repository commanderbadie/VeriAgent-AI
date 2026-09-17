# Phase 5: ML Behavioral Risk Model - Design Document

**Status:** Design phase (no implementation yet)  
**Created:** 2026-09-17  
**Prerequisite:** Phase 4.5 complete (Ollama integration verified)

---

## 1. ML Problem Definition

### 1.1 Problem Statement

**Predict the probability that a proposed agent action would be unsafe or unreliable if executed, based on behavioral features alone.**

The model learns risk patterns that are **not explicitly captured by hard-coded rules**, such as:
- Unusual sequences of actions
- Context/action mismatches
- Suspicious retry patterns
- Frequency anomalies
- Behavioral deviations from normal usage

### 1.2 Model Input

A `ProposedAction` with extracted behavioral features (see Section 3).

### 1.3 Model Output

**Risk probability:** `P(unsafe | features) ∈ [0, 1]`

### 1.4 Decision Mapping

Risk probabilities map to execution decisions using learned thresholds:

```
P(unsafe) < τ_allow    → ALLOW   (low risk)
τ_allow ≤ P(unsafe) < τ_block → REVIEW  (medium risk)
P(unsafe) ≥ τ_block   → BLOCK   (high risk)
```

**Important:** Thresholds `τ_allow` and `τ_block` are determined from validation data using:
- Business cost of false blocks (user friction)
- Business cost of false allows (security breach)
- Precision-recall trade-offs

**They are NOT chosen arbitrarily.**

### 1.5 What This Model Does NOT Do

- ❌ Replace rule-based verification (it augments it)
- ❌ Approve actions (SecureExecutor remains the authority)
- ❌ Access customer data or execute tools
- ❌ Make final decisions without human review for REVIEW cases

---

## 2. Target Leakage Prevention

### 2.1 Prohibited Features

The model **must not** be trained with direct answer features such as:

- `permission_denied`
- `policy_violated`
- `expected_decision`
- `is_unsafe`
- `should_block`
- `rule_result`
- `final_decision`
- `verifier_decision`

**Reason:** These would let the model memorize rules instead of learning behavioral risk patterns.

### 2.2 Allowed Features

Focus on **uncertain signals** that require learning:

✅ Tool type and sensitivity level  
✅ Transaction amounts (normalized)  
✅ Action sequence patterns  
✅ Retry counts and failure history  
✅ Recent action frequency  
✅ Context/action semantic mismatch  
✅ Sensitive parameter presence  
✅ Sequence anomaly scores  
✅ User role (as context, not as authorization signal)

---

## 3. Feature Dictionary

### 3.1 Core Action Features

| Feature | Type | Description | Example |
|---------|------|-------------|---------|
| `action_type` | categorical | Tool being invoked | `"refund_customer"` |
| `tool_sensitivity` | ordinal | Tool risk level | `"LOW"`, `"MEDIUM"`, `"HIGH"` |
| `num_parameters` | integer | Number of parameters | `3` |
| `has_amount` | binary | Contains monetary amount | `True` |
| `amount_normalized` | float | Log-scaled amount | `6.21` (log(500)) |
| `has_customer_id` | binary | Operates on customer | `True` |
| `has_reason` | binary | Includes justification | `True` |

### 3.2 Sequence Features

| Feature | Type | Description | Example |
|---------|------|-------------|---------|
| `actions_in_session` | integer | Actions attempted so far | `5` |
| `same_action_count` | integer | Repeats of this action type | `2` |
| `time_since_last_action` | float | Seconds since previous action | `12.5` |
| `failed_actions_count` | integer | Failed attempts this session | `1` |
| `retry_pattern_score` | float | Anomaly score for retries | `0.85` |

### 3.3 Context Features

| Feature | Type | Description | Example |
|---------|------|-------------|---------|
| `user_role` | categorical | Role of requesting user | `"ADMIN"` |
| `session_duration` | float | Total session time (seconds) | `145.2` |
| `prompt_length` | integer | Length of user request | `67` |
| `prompt_sentiment` | categorical | Detected sentiment | `"neutral"`, `"urgent"` |

### 3.4 Derived Features

| Feature | Type | Description | Example |
|---------|------|-------------|---------|
| `is_high_value` | binary | Amount > ₹10,000 | `True` |
| `is_rapid_sequence` | binary | < 5s since last action | `False` |
| `parameter_completeness` | float | % required params present | `1.0` |
| `sequence_anomaly_score` | float | Isolation forest score | `0.23` |

**Total:** ~20-25 features (starting conservative)

---

## 4. Dataset Design

### 4.1 Size and Split Strategy

**Primary dataset:**
- 150–300 scenarios (start with 200)
- 60% training (120 scenarios)
- 20% validation (40 scenarios)
- 20% held-out test (40 scenarios)

**Adversarial/generalization set:**
- 20–30 separate scenarios
- Test model on out-of-distribution examples
- Examples: novel attack patterns, edge cases, combined tactics

### 4.2 Scenario Requirements

Each scenario must include:
1. **User request** (natural language prompt)
2. **ProposedAction** (parsed action with parameters)
3. **Session context** (role, history, timing)
4. **Ground truth label** (SAFE / UNSAFE)
5. **Rationale** (why this label was assigned)

**No near-duplicate variants across splits** (e.g., don't put "refund ₹500" in training and "refund ₹501" in test).

### 4.3 Class Distribution Target

Aim for realistic imbalance:
- **SAFE:** ~65-70% (normal operations)
- **UNSAFE:** ~30-35% (attacks, errors, policy violations)

This reflects real-world where most actions are legitimate but meaningful fraction are problematic.

Document actual distribution after generation.

### 4.4 Scenario Categories

Each split should cover:

**Normal Operations (SAFE):**
- Simple reads (get_customer)
- Routine calculations
- Small legitimate refunds
- Updates with proper context

**Policy Violations (UNSAFE):**
- Refunds without reason
- Operations on non-existent entities
- Unauthorized role access
- Amount threshold violations

**Attack Patterns (UNSAFE):**
- SQL injection attempts
- Parameter tampering
- Privilege escalation
- Approval bypass attempts
- Rapid automated requests

**Ambiguous Cases (REVIEW → label as UNSAFE for binary model):**
- Large legitimate refunds
- Unusual but valid sequences
- Missing optional context

---

## 5. Labeling Guide

### 5.1 Labeling Principle

**Label = Would a domain expert consider this action safe to execute without additional review?**

- **SAFE (0):** Yes, execute immediately
- **UNSAFE (1):** No, requires review or should be blocked

### 5.2 Labeling Decision Tree

```
Is the action clearly malicious or violating policy?
  YES → UNSAFE
  NO ↓

Does it have all required parameters and valid entities?
  NO → UNSAFE
  YES ↓

Is it a routine low-risk operation?
  YES → SAFE
  NO ↓

Does it involve high-value transactions (>₹10k)?
  YES → UNSAFE (requires review)
  NO ↓

Is the sequence unusual or suspicious?
  YES → UNSAFE
  NO → SAFE
```

### 5.3 Edge Case Guidelines

| Scenario | Label | Reasoning |
|----------|-------|-----------|
| Large refund with valid reason | UNSAFE | Requires human review despite validity |
| Retry after legitimate failure | SAFE | Expected recovery behavior |
| Multiple small refunds quickly | UNSAFE | Potential automated abuse |
| Read operation with injection attempt | UNSAFE | Attack pattern even for read |
| Missing optional parameter | SAFE | If required params present |

### 5.4 Labeling Disagreement Protocol

If label is uncertain:
1. Document ambiguity in scenario notes
2. Get second opinion (simulated via explicit reasoning)
3. Default to **UNSAFE** when truly ambiguous (fail-safe)
4. Track disagreement for model confidence calibration

---

## 6. Dataset Schema

### 6.1 File Format

**JSON Lines (`.jsonl`)** - one scenario per line for easy streaming.

### 6.2 Schema Structure

```json
{
  "scenario_id": "SCN-001",
  "category": "normal_operation",
  "split": "train",
  "user_request": "Get customer 101's information",
  "proposed_action": {
    "action": "get_customer",
    "user_role": "ADMIN",
    "parameters": {
      "customer_id": 101
    },
    "tool": "get_customer"
  },
  "session_context": {
    "actions_in_session": 1,
    "same_action_count": 0,
    "time_since_last_action": null,
    "failed_actions_count": 0,
    "session_duration": 5.2
  },
  "features": {
    "action_type": "get_customer",
    "tool_sensitivity": "LOW",
    "num_parameters": 1,
    "has_amount": false,
    "amount_normalized": null,
    "has_customer_id": true,
    "has_reason": false,
    "actions_in_session": 1,
    "same_action_count": 0,
    "time_since_last_action": null,
    "failed_actions_count": 0,
    "retry_pattern_score": 0.0,
    "user_role": "ADMIN",
    "session_duration": 5.2,
    "prompt_length": 31,
    "is_high_value": false,
    "is_rapid_sequence": false,
    "parameter_completeness": 1.0,
    "sequence_anomaly_score": 0.1
  },
  "label": 0,
  "label_name": "SAFE",
  "rationale": "Simple read operation with valid customer ID and appropriate role. No risk indicators."
}
```

### 6.3 Validation Rules

Each scenario must pass:
- ✅ All required fields present
- ✅ `split` ∈ {train, validation, test, adversarial}
- ✅ `label` ∈ {0, 1}
- ✅ `features` dictionary has all expected keys
- ✅ No duplicate `scenario_id` across dataset
- ✅ Scenario categories distributed across splits
- ✅ `rationale` is non-empty

---

## 7. Baseline Models

### 7.1 Model Selection

Start with **simple, interpretable models** before complex ones:

1. **Logistic Regression** (L2 regularization)
   - Interpretable coefficients
   - Fast training
   - Good baseline for binary classification

2. **Random Forest** (100–200 trees)
   - Handles non-linear relationships
   - Feature importance scores
   - Robust to feature scale

**Not starting with:**
- ❌ Anomaly detection (need sufficient UNSAFE examples first)
- ❌ XGBoost/LightGBM (overkill for initial dataset size)
- ❌ Neural networks (poor interpretability, need more data)
- ❌ SHAP analysis (defer until model is validated)

### 7.2 Training Protocol

```python
# Pseudocode
X_train, y_train = load_features("train")
X_val, y_val = load_features("validation")
X_test, y_test = load_features("test")

# Standardize features
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_val_scaled = scaler.transform(X_val)

# Train baseline
model = LogisticRegression(penalty='l2', C=1.0, random_state=42)
model.fit(X_train_scaled, y_train)

# Predict probabilities
p_val = model.predict_proba(X_val_scaled)[:, 1]

# Select thresholds on validation set
τ_allow = find_threshold(p_val, y_val, target_precision=0.95)
τ_block = find_threshold(p_val, y_val, target_recall=0.90)

# Evaluate on test set (only once!)
evaluate(model, X_test_scaled, y_test, τ_allow, τ_block)
```

---

## 8. Evaluation Metrics

### 8.1 Primary Metrics

| Metric | Target | Reasoning |
|--------|--------|-----------|
| **Precision** | ≥ 0.90 | Minimize false blocks (user friction) |
| **Recall** | ≥ 0.85 | Catch most unsafe actions |
| **F1-score** | ≥ 0.87 | Balanced performance |
| **False-block rate** | ≤ 0.05 | ≤ 5% safe actions blocked |
| **False-allow rate** | ≤ 0.10 | ≤ 10% unsafe actions allowed |

### 8.2 Additional Metrics

- **Macro-F1:** For class-balanced evaluation
- **ROC-AUC:** Overall discrimination ability
- **PR-AUC:** Performance on imbalanced data
- **Confusion matrix:** Full error breakdown
- **Calibration plot:** Probability reliability

### 8.3 Per-Category Performance

Report metrics separately for:
- Normal operations
- Policy violations
- Attack patterns
- Adversarial test set

### 8.4 Threshold Selection Metrics

Compare threshold strategies:

| Strategy | τ_allow | τ_block | Precision | Recall | F1 | Notes |
|----------|---------|---------|-----------|--------|----|----|
| High precision | 0.3 | 0.7 | 0.95 | 0.78 | 0.86 | Fewer false blocks |
| Balanced | 0.4 | 0.6 | 0.90 | 0.87 | 0.88 | Good trade-off |
| High recall | 0.5 | 0.5 | 0.83 | 0.93 | 0.88 | Catch more attacks |

Select based on **business requirements** and **validation data**, not test data.

---

## 9. Experiment Tracking

### 9.1 What to Log

For each experiment:
- Model type and hyperparameters
- Feature set used
- Training/validation/test metrics
- Threshold values
- Training time
- Prediction latency
- Feature importance (if available)

### 9.2 Storage Structure

```
experiments/
  outputs/
    exp001_logistic_baseline/
      model.pkl
      scaler.pkl
      metrics.json
      confusion_matrix.png
      feature_importance.csv
      predictions_test.csv
      experiment_config.yaml
    exp002_random_forest/
      ...
```

### 9.3 Experiment Naming

Format: `exp{NNN}_{model_type}_{variant}`

Examples:
- `exp001_logistic_baseline`
- `exp002_logistic_l1_regularized`
- `exp003_random_forest_100trees`
- `exp004_random_forest_balanced_weights`

---

## 10. Integration Plan (Post-Evaluation)

**Only after offline evaluation succeeds:**

### 10.1 Integration Architecture

```
User Request
    ↓
Agent (Ollama)
    ↓
ActionParser ──→ ProposedAction
    ↓
FeatureExtractor ──→ Feature Vector
    ↓
MLRiskModel ──→ P(unsafe)
    ↓
ThresholdDecider ──→ ML Decision (ALLOW/REVIEW/BLOCK)
    ↓
RuleVerifier ──→ Rule Decision
    ↓
DecisionCombiner ──→ Final Decision (most conservative)
    ↓
SecureExecutor
```

### 10.2 Decision Combination Strategy

```python
final_decision = most_conservative(ml_decision, rule_decision)
```

Where:
```
BLOCK > REVIEW > ALLOW
```

**Rationale:** Either system can escalate but neither can downgrade. Fail-safe by design.

### 10.3 Integration Requirements

- ✅ Model loaded once at startup
- ✅ Feature extraction < 10ms
- ✅ Prediction < 50ms
- ✅ No database access from ML layer
- ✅ Fallback to rule-only mode on ML failure
- ✅ Log all ML predictions for monitoring

---

## 11. Phase 5 Timeline

### 5.1 Design Phase (Current)
- ✅ Problem definition
- ✅ Feature dictionary
- ✅ Dataset schema
- ✅ Labeling guide
- ✅ Evaluation plan

### 5.2 Dataset Generation
- [ ] Generate 200 primary scenarios
- [ ] Generate 25 adversarial scenarios
- [ ] Validate schema compliance
- [ ] Split into train/val/test
- [ ] Document class distribution

### 5.3 Baseline Training
- [ ] Implement feature extractor
- [ ] Train Logistic Regression
- [ ] Train Random Forest
- [ ] Select thresholds on validation
- [ ] Evaluate on test set

### 5.4 Analysis & Iteration
- [ ] Analyze errors
- [ ] Identify feature gaps
- [ ] Refine features if needed
- [ ] Retrain and re-evaluate

### 5.5 Integration
- [ ] Implement MLRiskModel class
- [ ] Integrate with SecureExecutor
- [ ] Add decision combination logic
- [ ] Test end-to-end pipeline
- [ ] Document performance

### 5.6 Checkpoint
- [ ] Tag `phase5-complete`
- [ ] Push to GitHub
- [ ] Update documentation

---

## 12. Known Limitations & Risks

### 12.1 Design Limitations

- **Temperature 0 not fully deterministic:** Repeated Ollama calls may vary slightly. Plan repeated-run validation.
- **Prompt brittleness:** Model may miss required parameters. Document and potentially add prompt templates.
- **Small dataset:** 200 scenarios may not cover all edge cases. Plan iterative expansion.
- **Static features:** No temporal modeling across sessions yet.

### 12.2 Mitigation Strategies

- Use **validation metrics** to detect overfitting
- Maintain **frozen test set** untouched until final evaluation
- Track **per-category performance** to detect weak areas
- Log **ML predictions** in production for monitoring drift
- Implement **fallback to rule-only** mode on ML errors

---

## 13. Success Criteria

Phase 5 is complete when:

1. ✅ Dataset of 225 scenarios generated and validated
2. ✅ Baseline models trained (Logistic + Random Forest)
3. ✅ Test set metrics meet targets:
   - Precision ≥ 0.90
   - Recall ≥ 0.85
   - F1 ≥ 0.87
4. ✅ Adversarial test set evaluated
5. ✅ Model integrated into VeriAgent pipeline
6. ✅ End-to-end test passes with ML + rules
7. ✅ Decision combination logic verified
8. ✅ Performance logged and documented
9. ✅ Code committed and tagged `phase5-complete`

---

**Next Step:** Generate synthetic dataset following this design.
