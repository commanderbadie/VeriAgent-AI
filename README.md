# VeriAgent

**A framework for reliable and safe AI-agent actions.**

VeriAgent is a final-year B.E. Computer Science research project investigating whether an independent verification layer can reduce unsafe, incorrect, and unauthorized AI-agent actions while maintaining acceptable task performance.

## Core flow

```text
User → AI Agent → Proposed Action → VeriAgent → ALLOW / REVIEW / BLOCK → Tool
```

VeriAgent does **not** claim to make AI agents completely safe. The project will empirically compare an unverified agent with rules-only, ML-only, and combined verification configurations.

## Core scope

- Synthetic business-operations environment
- Structured agent action proposals
- Permission and RBAC verification
- Data and parameter validation
- Configurable policy enforcement
- Security checks
- Learned behavioral risk scoring
- ALLOW / REVIEW / BLOCK decisions
- Reproducible evaluation, latency measurement, and failure analysis

## Planned zero-cost stack

- Python 3.11+
- SQLite
- pandas, NumPy, and scikit-learn
- FastAPI (backend)
- Streamlit (dashboard)
- Local/open-source LLM through an optional adapter

## Repository structure

```text
src/veriagent/       Core Python package
 tests/               Automated tests
 docs/                Scope and architecture
 data/                Synthetic data artifacts
 experiments/         Reproducible experiment outputs
```

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e .
python -m veriagent.demo
python -m unittest discover -s tests -v
```

## Research question

> Can an independent verification layer reduce incorrect, unsafe, and unauthorized actions performed by AI agents while maintaining acceptable task performance?

## Current status

Initial project scaffold: deterministic verification baseline, synthetic SQLite schema, demo, and tests.

## Academic integrity

Experimental results will be reported as observed. The project will not fabricate results, claim complete security, or make unsupported novelty claims.
