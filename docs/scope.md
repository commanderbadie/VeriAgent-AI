# MVP Scope

## Included

1. Controlled business-operations agent with 4–5 tools.
2. Synthetic SQLite data only.
3. Structured proposed actions that never execute before verification.
4. Deterministic permission, policy, parameter, and entity checks.
5. ML scoring for uncertain behavioral risk signals.
6. ALLOW, REVIEW, and BLOCK outcomes.
7. Baseline, rules-only, ML-only, and full-system experiments.
8. Frozen test set and separate adversarial/generalization set.
9. Security tests, latency analysis, false-block analysis, and failure cases.
10. Simple Streamlit dashboard and one indirect prompt-injection demonstration.

## Explicitly optional

- SHAP explanations
- Multiple LLM backends
- Drift detection
- Public benchmark release
- Cloud deployment
- Complex multi-agent orchestration

## ML boundary

Deterministic facts such as explicit permission denial, missing entities, and direct policy violations belong to the rules layer. The ML model should focus on uncertain behavioral patterns such as abnormal sequences, retries, frequency, context mismatch, and combinations of weak risk signals.

This separation is necessary to prevent target leakage and inflated evaluation results.
