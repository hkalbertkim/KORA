# KORA
## An Inference-First Execution Architecture

KORA is an execution system that reduces unnecessary LLM calls by structuring tasks before invoking inference.

Instead of treating large language models as the default compute engine,  
KORA treats inference as a bounded, callable service.

---

## Why KORA?

Modern AI systems:

- Call LLMs for every request
- Accumulate unnecessary token costs
- Lack execution-level governance
- Struggle with predictable latency

KORA changes this.

It executes deterministically first.
It calls LLMs only when necessary.
It enforces structured outputs and budgets.

---

## Core Principles

• Deterministic-first execution  
• Budget-constrained inference  
• Structured JSON outputs only  
• Task-level isolation and verification  
• Model-agnostic design  

---

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
python3 examples/hello_kora/run.py
python3 -m pytest -q
