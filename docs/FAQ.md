# Frequently Asked Questions

This FAQ addresses common questions and critiques about KORA.

It assumes familiarity with modern LLM systems.

---

## 1. Is KORA just a wrapper around an LLM?

No.

KORA does not modify model internals.
<br>It restructures how and when models are invoked.
<br>The difference is architectural, not cosmetic.

---

## 2. Does KORA improve model intelligence?

No.

KORA does not improve reasoning quality directly.
<br>It governs invocation discipline. It may reduce hallucination indirectly by limiting reasoning scope, but it does not change model weights.

---

## 3. Why not just use better prompt engineering?

Prompt engineering still assumes monolithic invocation.
<br>KORA addresses structural bundling before prompting begins.
<br>The issue is not prompt quality. It is invocation reflexivity.

---

## 4. Isn't decomposition already used in agents?

Many agents decompose tasks heuristically.
<br>KORA makes decomposition structural and mandatory.

The difference is:

- Explicit Task IR
- Explicit budget enforcement
- Explicit schema validation
- Formal DAG execution

Heuristic decomposition is not the same as architectural decomposition.

---

## 5. What if most tasks require reasoning?

Then P is low.

If deterministic proportion P approaches zero, KORA provides limited economic benefit.
<br>KORA is conditionally advantageous, not universally dominant.

See break-even-model.md.

---

## 6. Does decomposition hurt reasoning coherence?

It can.

Poorly designed task boundaries may fragment semantic context.
<br>Decomposition must preserve reasoning integrity.
<br>This is an active research question.

See research-agenda.md.

---

## 7. Is the overhead worth it?

Structural overhead O must remain bounded.

If O exceeds savings from reduced model usage, KORA is not beneficial.
<br>Break-even is measurable. KORA is falsifiable.

---

## 8. Does KORA require distributed execution?

No.

Distributed execution is optional.
<br>KORA functions locally.
<br>Distribution becomes possible because of atomic tasks.

---

## 9. Why emphasize CPU?

Because deterministic tasks dominate many workflows.
<br>Executing deterministic components on CPU reduces model load.
<br>CPU-first does not mean GPU-free.

It means compute-neutral.

---

## 10. Is this anti-GPU?

No.

KORA is not anti-accelerator. It is anti-reflex.

Heavy reasoning tasks may still require powerful models.
<br>KORA reduces unnecessary invocation, not capability.

---

## 11. Could large models eventually eliminate need for structure?

Larger models increase reasoning capacity.
<br>They do not eliminate the distinction between necessary and unnecessary inference. 
<br>Structure remains relevant regardless of model size.

---

## 12. Is this over-engineering?

That depends on workload.

For small prototypes, reflexive invocation is simple.
<br>For scaled systems, structural discipline becomes critical.

KORA targets scalable systems.

---

## 13. Is KORA a framework?

No.

It is an architectural pattern implemented as a system.
<br>It may be implemented as a library, service, or distributed fabric.

The architecture is primary.

---

## 14. Is this research or production?

Both.

The core architecture is production-ready.
<br>The DNFM direction remains research.

---

## 15. What makes KORA different?

Three things:

- Determinism before inference
- Native decomposition as law
- Budget as contractual boundary

Many systems approximate one of these.

Few enforce all three structurally.

---

## 16. What happens if KORA is wrong?

If decomposition does not yield measurable savings, or overhead dominates, 
<br>the architecture must adapt.

KORA does not claim inevitability.
It claims conditional structural advantage.

---

## Closing Position

KORA does not claim to replace models.
<br>It claims that reasoning without structure is fragile.
<br>Structure disciplines intelligence.

**Reflex is convenient.  
Structure is durable.**
