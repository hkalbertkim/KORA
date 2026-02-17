# KORA Runtime Architecture (v1 Boundary Specification)

This document defines the **formal runtime boundaries** for KORA v1.

This is not philosophical architecture.
This is executable contract architecture.

---

# 1. Runtime Module Topology

Current code structure:

kora/
- task_ir.py
- scheduler.py
- executor.py
- budget.py
- verification.py
- adapters/
    - base.py
    - openai_adapter.py
    - mock.py

The runtime is divided into four formal layers.

---

# 2. Layer Definitions

## 2.1 IR Layer

File:
- kora/task_ir.py

Responsibility:
- Define Task and TaskGraph structures
- Encode task metadata
- Encode dependency relationships
- Contain zero external I/O
- Contain zero adapter awareness

IR layer must:
- Not import adapters
- Not invoke execution
- Not enforce budget
- Not perform schema validation

It defines structure only.

---

## 2.2 Execution Engine

Files:
- kora/scheduler.py
- kora/executor.py

Scheduler responsibility:
- DAG validation
- Topological ordering
- Detect cyclic graphs

Executor responsibility:
- Deterministic-first execution
- Decide whether model invocation is required
- Orchestrate budget enforcement
- Orchestrate retry and escalation
- Invoke adapters when required

Executor must:
- Never contain provider-specific logic
- Never contain schema rules
- Delegate all I/O to adapters
- Delegate validation to verification layer

---

## 2.3 Governance Layer

Files:
- kora/budget.py
- kora/verification.py

Budget module:
- Enforce max_tokens
- Enforce max_time_ms
- Enforce max_retries
- Provide breach signals (not recovery policy)

Verification module:
- Validate structured output
- Enforce strict schema
- Disallow additionalProperties
- Return validation errors, not recovery logic

These modules must not:
- Call adapters
- Modify execution policy
- Perform retries

They signal.
Executor decides.

---

## 2.4 Adapter Layer

Files:
- kora/adapters/base.py
- kora/adapters/openai_adapter.py
- kora/adapters/mock.py

Adapter layer is pure I/O.

Responsibilities:
- Convert structured task into provider request
- Return structured result
- Return token usage metadata

Adapters must not:
- Implement retry logic
- Implement budget logic
- Implement validation logic
- Know about scheduler
- Know about DAG

They are stateless connectors.

---

# 3. Dependency Rules

Allowed imports:

IR → (no runtime imports)
Scheduler → IR
Executor → IR, Scheduler, Budget, Verification, Adapters
Budget → none
Verification → none
Adapters → none (except external provider SDKs)

Forbidden:
IR importing adapters
Adapters importing executor
Verification importing scheduler
Budget importing adapters

---

# 4. Execution Flow (Runtime-Accurate)

```mermaid
flowchart TD
    A[Input] --> B[Task IR]
    B --> C[Scheduler: DAG Validation]
    C --> D[Executor Loop]
    D --> E{Deterministic?}
    E -->|Yes| F[Local Execution]
    E -->|No| G[Budget Check]
    G --> H[Adapter Invocation]
    H --> I[Schema Validation]
    I --> J[Retry / Escalation Decision]
    J --> K[Aggregate Results]
    K --> L[Return Output]
