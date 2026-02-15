# System Diagram

This document visualizes KORA as a layered execution system.

The diagrams are not decorative.  
They clarify structural boundaries.

---

## 1. Layered Architecture

```mermaid
flowchart TD
    A[User Input]
    A --> B[Task Construction Layer]
    B --> C[DAG Validation Layer]
    C --> D[Deterministic Execution Layer]
    D --> E[Reasoning Adapter Layer]
    E --> F[Model Layer]
    F --> G[Schema Validation Layer]
    G --> H[Aggregation Layer]
    H --> I[Final Output]
```

Each layer has a single responsibility.

**No layer bypasses another.**

---

## 2. Task Graph Structure

```mermaid
flowchart LR
    A[Request]
    A --> B1[Deterministic Task 1]
    A --> B2[Model Task 1]
    B2 --> B3[Model Task 2]
    B1 --> C[Aggregation]
    B3 --> C
    C --> D[Output]
```

This graph shows:

- Deterministic tasks execute locally.
- Model tasks execute selectively.
- Aggregation recombines outputs.
- Failures remain isolated.

---

## 3. Routing Architecture

```mermaid
flowchart TD
    A[Atomic Task]
    A -->|Deterministic| B[CPU Execution]
    A -->|Lightweight Reasoning| C[Local Small Model]
    A -->|Heavy Reasoning| D[Remote LLM]
```

Routing decisions are policy-driven.

Tasks are movable because they are atomic.

**Decomposition enables routing.**

---

## 4. Budget Enforcement Lifecycle

```mermaid
flowchart TD
    A[Model Task]
    A --> B[Pre-Invocation Budget Check]
    B --> C[Invocation]
    C --> D[Runtime Monitor]
    D --> E[Schema Validation]
    E --> F{Within Budget?}
    F -->|Yes| G[Complete]
    F -->|No| H[Terminate]
```

Inference cannot escape governance.

Budget enforcement exists at multiple checkpoints.

---

## 5. Distributed Execution Fabric

```mermaid
flowchart LR
    A[Global Task Graph]
    A --> B[Node 1 CPU]
    A --> C[Node 2 Edge Device]
    A --> D[Node 3 Remote LLM]
    B --> E[Partial Results]
    C --> E
    D --> E
    E --> F[Final Aggregation]
```

This illustrates long-term direction:

- Tasks may execute across nodes.
- Atomic structure enables distribution.
- Aggregation preserves coherence.

---

## 6. Structural Comparison

### Inference-Reflexive Model

```mermaid
flowchart LR
    A[Input] --> B[Prompt]
    B --> C[Model]
    C --> D[Output]
```

### Structured KORA Model

```mermaid
flowchart TD
    A[Input]
    A --> B[Task Graph]
    B --> C[Deterministic Execution]
    B --> D[Selective Model Invocation]
    C --> E[Aggregation]
    D --> E
    E --> F[Validated Output]
```

The difference is not capability.

The difference is structural governance.

---

## 7. Execution Guarantees Summary

| Property | Description |
|----------|-------------|
| Deterministic-first | Trivial tasks never invoke model |
| Budget-bound | No unbounded inference |
| Schema-validated | Output must match contract |
| Atomic tasks | Failures are localized |
| Routing-capable | Tasks may execute on heterogeneous compute |

These guarantees emerge from structure, not configuration.

---

## Closing View

KORA is not centered on the model.

It is centered on structure.

Models are invoked when necessary.  
Tasks are routed when possible.  
Budgets are enforced always.

**Structure governs execution.**
