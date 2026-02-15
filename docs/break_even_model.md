# Break-Even Model

KORA reduces unnecessary inference calls.

To formalize this, define:

| Symbol | Meaning                          |
|--------|----------------------------------|
| C      | Cost per LLM call                |
| P      | Proportion of trivial requests   |
| T      | Total number of requests         |

---

## Cost Model

| Scenario | Formula              |
|----------|----------------------|
| Direct   | C * T                |
| KORA     | C * (1 - P) * T      |
| Savings  | C * P * T            |

---

## Interpretation

If P > 0.5, then more than half of all LLM calls are unnecessary.

In such systems, KORA cuts cost proportionally to P.

---

## Real Benchmark Example

From v0.1-alpha benchmark:

| Metric     | Direct | KORA | Reduction |
|------------|--------|------|-----------|
| LLM Calls  | 2      | 1    | -50%      |
| Tokens In  | 359    | 225  | -37%      |
| Tokens Out | 121    | 85   | -30%      |

---

## Production Implication

In workloads where trivial requests dominate:

If P approaches 0.6 - 0.8:

- Direct systems scale linearly with inference cost.
- KORA scales with structured execution cost plus bounded inference.

This produces significant long-term operational savings.
