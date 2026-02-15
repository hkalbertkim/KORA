
---

# 📄 2️⃣ `docs/benchmark.md`

```markdown
# KORA v0.1 Benchmark Report
## Inference Reduction under Structured Task Execution

**Version:** v0.1-alpha  
**Date:** March 8, 2025  
**Model:** gpt-4o-mini  
**Reproducibility Commit:** (insert git rev-parse --short HEAD)

---

## Objective

Evaluate KORA’s ability to reduce unnecessary inference while preserving the capability for complex tasks.

---

## Setup

Model: gpt-4o-mini  
Structured JSON schema enforced  
Deterministic pre-classification before LLM invocation  

Two input cases:
1. Short request
2. Long request

---

## Results

### Short Case

| Metric     | Direct | KORA |
|------------|--------|------|
| LLM Calls  | 1      | 0    |
| Tokens In  | 135    | 0    |
| Tokens Out | 41     | 0    |

KORA avoided 100% of LLM usage.

---

### Long Case

| Metric     | Direct | KORA |
|------------|--------|------|
| LLM Calls  | 1      | 1    |
| Tokens In  | 224    | 225  |
| Tokens Out | 80     | 85   |

KORA incurred negligible overhead due to structured validation.

---

## Aggregate


| Metric     | Direct | KORA | Delta |
|------------|--------|------|-------|
| LLM Calls  | 2      | 1    | -50%  |
| Tokens In  | 359    | 225  | -37%  |
| Tokens Out | 121    | 85   | -30%  |

---

## Interpretation

KORA does not outperform the model.

It changes when inference happens.

Trivial requests avoid LLM invocation.
Complex requests remain supported.

---

## Reproducibility

```bash
python3 examples/direct_vs_kora/run.py
