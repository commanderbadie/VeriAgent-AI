# Initial Architecture

```text
User request
    ↓
Agent / action generator
    ↓
ProposedAction (structured, not executed)
    ↓
┌──────────────────────────────────────────┐
│ VeriAgent                                │
│  1. Permission check                     │
│  2. Parameter and entity validation      │
│  3. Policy check                         │
│  4. Security checks                      │
│  5. Behavioral ML risk score             │
│  6. Decision fusion                      │
└──────────────────────────────────────────┘
    ↓
ALLOW / REVIEW / BLOCK
    ↓
Tool executor (ALLOW only; REVIEW needs approval)
    ↓
Audit log and outcome
```

## Design principles

- Verification is independent of the chosen LLM.
- Tools accept only validated structured parameters.
- Deterministic failures cannot be overridden by a low ML risk score.
- Every decision records its checks, reasons, timing, and eventual outcome.
- Evaluation can replay fixed scenarios without repeatedly calling an LLM.
- The unverified baseline and each ablation use the same scenario inputs.

## First implementation milestone

The initial scaffold implements domain models, deterministic verification, a synthetic SQLite schema, a command-line demonstration, and automated tests. ML, API, dashboard, and experiment runners will be added incrementally after the action contract and policies are frozen.
