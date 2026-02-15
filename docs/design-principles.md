# Design Principles

KORA is governed by structural principles.

These principles are not guidelines.  
They are architectural constraints.

---

## 1. Determinism Before Inference

If a task can be resolved deterministically, it must not invoke a model.

Probabilistic reasoning is escalation, not default.

**No hidden inference.**

---

## 2. Tasks Are Atomic

The smallest execution unit is a Task IR object.

Tasks must be:

- Typed
- Bounded
- Schema-constrained
- Dependency-aware

Monolithic prompts are architectural regression.

---

## 3. Budget Is Contract

All model-bound tasks must declare:

- max_tokens
- max_time_ms
- max_retries

Budget must be enforced.

Unbounded reasoning is structural failure.

---

## 4. Validation Is Mandatory

All model outputs must pass strict schema validation.

No implicit trust.<br>
No best-effort parsing.<br>
No silent format acceptance.

Verification precedes aggregation.

---

## 5. Structure Precedes Scale

Scaling without structure amplifies cost and instability.
<br>Decomposition and routing must exist before distributed expansion.
<br>Parallelism is enabled by structure, not by hardware alone.

---

## 6. Compute Is Substrate

KORA does not bind intelligence to hardware class.

Tasks may execute on:

- CPU
- Local models
- Remote models
- Distributed nodes

Routing is architectural.

Hardware is interchangeable.

---

## 7. Observability Is Structural

Every task must emit telemetry.
<br>Every model call must be logged.
<br>Every retry must be visible.

If it cannot be measured, it cannot be governed.

---

## 8. No Architectural Drift

New features must not:

- Reintroduce inference reflexivity
- Remove budget enforcement
- Weaken validation
- Obscure task boundaries
- Introduce vendor lock-in

Convenience does not override invariants.

---

## 9. Decomposition Is Native

Decomposition is not optional optimization.

It is the foundation of:

- Cost reduction
- Routing flexibility
- Failure isolation
- Decentralization

If decomposition weakens, architecture collapses.

---

## 10. Falsifiability Over Assumption

KORA makes measurable claims.

Every structural improvement must be:

- Observable
- Quantifiable
- Reversible if disproven

Architecture must survive experiment.

---

## Closing Principle

KORA does not compete on model size.

It competes on structural discipline.

**Structure first.  
Scale second.**
