# Public vs Private Responsibility Matrix

Status: Boundary Lock Document v1.0  
Purpose: Clearly define what is Open (public contract) and what is Closed (private policy) across KORA, KORA Studio, and Krako 2.0.

---

# 1. High-Level Structural Model

Architecture Stack:

KORA (Open – Execution Intelligence)
        ↓
Krako Contract Layer (Open – Public Interface)
        ↓
Krako Fabric Core (Closed – Infrastructure & Policy)

This document freezes that separation.

---

# 2. KORA (Fully Open Source)

## 2.1 Public and Authoritative

The following are PUBLIC and must remain open:

• Task IR schema  
• TaskGraph structure  
• DAG validation rules  
• Deterministic-first execution model  
• Budget governance semantics  
• Schema validation contract  
• Reasoning Adapter interface  
• Stage semantics  
• Telemetry model (task-level)  
• Benchmark harness  
• Break-even and performance models  

KORA defines semantic meaning.
Krako must conform to it.

---

# 3. Krako Contract Layer (Open)

This layer connects KORA to distributed execution.

## 3.1 Must Be Public

• WorkUnit JSON schema  
• TaskGraph ingestion API  
• ExecutionSession schema  
• Canonical Event Envelope  
• Event type taxonomy  
• Budget non-increase invariant  
• Retry cap contract  
• Stop-reason taxonomy  
• Determinism & replay guarantees  

These are CONTRACTS.
They are transparent and versioned.

---

# 4. Krako Fabric Core (Closed)

This is where competitive advantage resides.

## 4.1 Must Remain Private

• Scheduler scoring weights  
• Placement heuristics  
• Congestion control tuning  
• Autoscaling controller internals  
• Trust scoring algorithm details  
• Billing engine implementation  
• Ledger reconciliation engine  
• Capacity topology & infra deployment  
• Pod orchestration logic  
• Admission control thresholds  

These are POLICIES.
They may evolve without changing contracts.

---

# 5. KORA Studio Scope (Open Distribution)

KORA Studio includes:

• KORA core engine  
• Local deterministic executor  
• Local model adapter  
• Local telemetry  
• Browser UI (chat)  
• Local API server  

KORA Studio explicitly EXCLUDES:

• Distributed scheduling  
• Ledger & billing  
• Trust scoring  
• Autoscaling  
• Admission control  
• Multi-node coordination  

Studio must operate without Krako.

---

# 6. Responsibility Table

| Component | Open | Closed | Authority |
|------------|------|--------|-----------|
| Task IR | Yes | No | KORA |
| Budget semantics | Yes | No | KORA |
| Stage taxonomy | Yes | No | KORA |
| WorkUnit schema | Yes | No | Contract |
| Event envelope | Yes | No | Contract |
| Scheduler scoring | No | Yes | Fabric |
| Autoscaling logic | No | Yes | Fabric |
| Trust algorithm | No | Yes | Fabric |
| Billing ledger internals | No | Yes | Fabric |
| Studio runtime | Yes | No | KORA |

---

# 7. Invariant Protection Rules

The following rules prevent duplication:

1. KORA must never depend on Fabric internals.  
2. Fabric must never redefine Task IR semantics.  
3. Studio must not embed Fabric policy logic.  
4. Contracts must remain versioned and stable.  
5. Private policy changes must not alter public invariants.  

---

# 8. Versioning Implications

Open layers follow semantic versioning.
Closed layers may evolve independently as long as:

• Contracts are honored  
• Determinism guarantees preserved  
• Budget invariants preserved  

---

# 9. Strategic Outcome

KORA becomes:

• Public execution standard  
• Decomposition reference implementation  
• Studio runtime engine  

Krako becomes:

• Scalable execution infrastructure  
• Revenue-generating fabric  
• Performance-optimized substrate  

Clear separation eliminates:

• Code duplication  
• Responsibility drift  
• Architectural confusion  
• Product positioning ambiguity  

---

# Closing Position

Contracts are public.  
Policies are private.  
Structure is open.  
Scale is proprietary.

This boundary must not blur.

