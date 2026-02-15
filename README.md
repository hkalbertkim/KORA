# KORA
## Inference-First Execution Architecture

KORA is an execution architecture that structures and routes intelligence before invoking large language models.

Instead of calling an LLM for every request,  
KORA executes deterministically first, applies explicit budgets, and invokes inference only when necessary.

---

## Why KORA?

Modern AI systems are inference-reflexive:
they default to large model invocation even when not required.

This leads to:

- Unnecessary token consumption
- Unpredictable latency
- Poor cost transparency
- Over-centralization of compute

KORA introduces execution discipline.

---

## What KORA Does

• Deterministic-first task execution  
• Explicit task graphs (DAG)  
• Budget-constrained inference  
• Structured JSON output enforcement  
• Retry and verification policies  
• Model-agnostic adapter architecture  

---

## Roadmap

KORA evolves in phases:

### Phase 1 - Inference Minimization (current)
Reduce unnecessary LLM calls.

### Phase 2 - Task Decomposition
Split large requests into atomic subtasks.

### Phase 3 - Distributed Routing
Route subtasks across heterogeneous systems.

### Phase 4 - Compute-Neutral AI
Enable AI execution in CPU-only and resource-constrained environments.

---

## Benchmark

Across short and long cases:

| Metric      | Direct | KORA | Reduction |
|-------------|--------|------|-----------|
| LLM Calls   | 2      | 1    | -50%      |
| Tokens In   | 359    | 225  | -37%      |
| Tokens Out  | 121    | 85   | -30%      |

See `docs/benchmark.md`.

---

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
python3 examples/hello_kora/run.py
python3 examples/direct_vs_kora/run.py
