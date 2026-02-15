# Architecture

## Execution Flow

1. User input
2. Task IR generation
3. DAG validation
4. Deterministic execution
5. Budget evaluation
6. Adapter invocation (if required)
7. Schema validation
8. Retry / fail policy
9. Result aggregation

---

## Components

- Task IR
- Scheduler
- Budget Engine
- Deterministic Executor
- Reasoning Adapter
- Verification Layer

---

## Design Principles

Loose coupling via HTTP adapters.

Structured JSON outputs only.

Task-level failure isolation.

Inference treated as callable service.
