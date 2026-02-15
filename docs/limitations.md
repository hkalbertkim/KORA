# Limitations

KORA is not universally superior.

Its advantages depend on structural conditions. This document outlines the architectural, economic, and practical limitations of the system.

---

## 1. Dependence on Decomposition Quality

KORA assumes that a meaningful portion of requests are:

- Deterministic
- Decomposable
- Structurally separable

If decomposition quality is poor:

- Deterministic coverage decreases.
- Model invocation frequency remains high.
- Structural overhead may dominate.

In domains where most tasks require deep reasoning with minimal deterministic structure, gains may be limited.

Decomposition accuracy is foundational.

---

## 2. Structural Overhead

KORA introduces additional processing:

- Task construction
- DAG validation
- Schema validation
- Telemetry emission

Let O represent structural overhead per request.
<br><br>
If:  P * C_m <= O
<br><br>
where P is deterministic proportion and C_m is model cost, then KORA does not provide economic benefit.

Overhead must remain controlled.

---

## 3. Latency Sensitivity

While deterministic execution is typically faster than model inference, <br>structural overhead may impact ultra-low-latency systems.

In environments where:

- Model calls are extremely fast
- Request complexity is minimal
- Latency requirements are sub-millisecond

the structural layer may introduce measurable delay. KORA prioritizes discipline over micro-optimization.

---

## 4. Increased System Complexity

Compared to direct model invocation, KORA introduces:

- Task graph construction
- Explicit routing logic
- Budget enforcement mechanisms
- Validation layers

This increases:

- Codebase complexity
- Cognitive load
- Maintenance requirements

Simplicity of invocation is traded for structural control.

---

## 5. Schema Rigidity

Strict schema validation ensures output discipline.

However:

- Creative tasks may require flexible output formats.
- Overly rigid schemas may constrain exploratory reasoning.
- Excessive validation may increase retry frequency.

Balance must be maintained between validation strictness and flexibility.

---

## 6. Retry Amplification Risk

While retries are bounded, certain tasks may:

- Repeatedly fail schema validation
- Trigger escalation logic
- Consume retry budget inefficiently

Poorly designed schemas or prompt templates can amplify retry cost.

Retry policy must be tuned carefully.

---

## 7. Model Capability Assumptions

KORA assumes that model tasks can be isolated effectively.

In some reasoning scenarios:

- Decomposition may fragment reasoning context.
- Cross-task coherence may degrade.
- Aggregation may introduce inconsistency.

Large, holistic reasoning tasks may not decompose cleanly.

Decomposition must preserve semantic coherence.

---

## 8. Distributed Execution Complexity

Decentralized routing introduces new challenges:

- Node trust
- Network reliability
- Task serialization overhead
- Partial failure coordination

Distributed CPU routing is architecturally viable, but operationally complex.

Compute neutrality increases system surface area.

---

## 9. DNFM Uncertainty

Decomposition-Native Foundation Models remain speculative.

Risks include:

- Reduced reasoning quality under strict task segmentation
- Difficulty training models on graph-native inputs
- Over-constrained reasoning patterns

DNFM direction is research, not guarantee.

---

## 10. Economic Assumptions

The break-even model assumes:

- Model cost remains significant relative to deterministic cost.
- Deterministic coverage remains meaningful.

If model cost decreases dramatically or hardware becomes ubiquitous, economic advantage may shift.

KORA optimizes for structural control, not short-term cost alone.

---

## 11. Governance Burden

Strong architectural invariants require:

- Careful code review
- Strict contribution discipline
- Active governance enforcement

Without governance rigor, structure degrades over time.

Architecture demands stewardship.

---

## 12. Not a Replacement for Models

KORA does not:

- Improve base model reasoning quality
- Eliminate hallucination in model tasks
- Replace training or fine-tuning strategies

It governs invocation, not capability.

---

## 13. Conditional Superiority

KORA is beneficial when:

- Deterministic proportion is meaningful
- Structural overhead is controlled
- Budget governance is enforced
- Routing flexibility is utilized

It is not universally superior.

It is structurally advantageous under measurable conditions.

---

## Closing Position

Architecture is tradeoff.

KORA trades simplicity of invocation for structural control.

It trades monolithic convenience for disciplined composition.

These tradeoffs are deliberate.

**Structure improves control.  
Control increases responsibility.**
