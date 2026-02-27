# KORA–Krako 2.0 Alignment & KORA Studio Baseline Plan

Status: Strategic Consolidation Draft  
Purpose: Eliminate duplication between KORA and Krako 2.0, define clear responsibility boundaries, and establish a stable baseline for KORA Studio (personal runtime distribution).

---

# 0. Structural Dependency Clarification (Very Important)

Before discussing alignment, we must clarify the structural dependency graph.

Originally:

• KORA was conceived as an independent execution architecture.
• Krako 2.0 was later built as a distributed execution fabric.

Because Krako needed deterministic-first orchestration, KORA logic was embedded conceptually inside Krako’s control layer.

This created confusion:

Is KORA a subsystem of Krako?
Or is Krako an execution backend for KORA?

The correct structural model is the following.

---

## 0.1 Canonical Dependency Direction

The dependency must flow in exactly one direction:

Application
    ↓
KORA (Control Plane / Execution Intelligence)
    ↓
Krako 2.0 (Data Plane / Distributed Fabric)

Never the reverse.

Krako must never depend on KORA internals.
KORA may target Krako as one execution backend.

This preserves conceptual clarity.

---

## 0.2 Three Deployment Modes (To Remove Confusion)

KORA can operate in three modes:

Mode A — Standalone (Local Studio)
    KORA = Control + Local Execution Engine
    No Krako involved.

Mode B — Fabric-Backed
    KORA = Control Plane
    Krako = Execution Fabric

Mode C — Embedded Product View
    A product (Krako Platform) bundles:
        • KORA (control subsystem)
        • Krako Fabric (execution subsystem)

In Mode C, KORA appears "inside" Krako as a subsystem.
Architecturally, however, dependency direction must remain:

KORA defines tasks.
Krako executes tasks.

---

## 0.3 Why Confusion Happened

Confusion emerged because:

• KORA was built first as architecture.
• Krako 2.0 later implemented many runtime concerns.
• Some control semantics (retry, budget enforcement, routing) were implemented inside Krako.

This made it appear that KORA was absorbed.

To correct this:

We must treat KORA as the specification authority for:

• Task IR
• Escalation semantics
• Budget declaration
• Schema enforcement semantics
• Stage semantics

Krako must treat these as external contracts.

---

# 1. Current Situation Summary

We now have two fully articulated systems:

## 1.1 KORA (Execution Intelligence Engine)

KORA defines:

• Philosophy (Determinism Before Inference)  
• Task IR contract  
• DAG execution model  
• Budget governance  
• Schema validation  
• Reasoning adapter abstraction  
• Telemetry + falsifiability  
• Distributed execution protocol (role-based)  

KORA is structurally complete as an execution architecture.

---

## 1.2 Krako 2.0 (Distributed Execution Fabric)

Krako defines:

• ExecutionSession lifecycle  
• WorkUnit contract  
• Scheduler semantics  
• Node Agent protocol  
• LLM Pod interface  
• Billing & ledger  
• Trust scoring  
• Autoscaling & admission control  
• Event-sourced telemetry backbone  

Krako is a distributed infrastructure runtime.

---

# 2. The Core Risk: Architectural Duplication

If not aligned properly, the following duplication risks exist:

• Retry logic implemented in both KORA and Krako  
• Budget enforcement in both layers  
• Escalation logic drifting into Krako  
• Verification logic duplicated  
• Telemetry taxonomy mismatch  
• Decomposition logic re-implemented in fabric layer  

This would break:

• Determinism guarantees  
• Budget invariants  
• Replay safety  
• Architectural clarity  

---

# 3. Final Role Separation (Must Be Locked)

## 3.1 KORA = Control Plane (Execution Intelligence)

KORA owns:

• Task IR definition  
• Decomposition  
• Escalation logic  
• Budget declaration  
• Schema contracts  
• Verification semantics  
• Stage semantics  
• Deterministic-first enforcement  

KORA must NOT:

• Perform distributed scheduling  
• Manage node capacity  
• Implement billing  
• Implement trust scoring  
• Implement autoscaling  
• Maintain execution ledger  

KORA decides WHAT and WHY.

---

## 3.2 Krako 2.0 = Data Plane (Execution Fabric)

Krako owns:

• ExecutionSession creation  
• WorkUnitExecution lifecycle  
• Placement and scheduling  
• Retry timing & congestion control  
• Node health and trust usage  
• Billing & ledger replay  
• Autoscaling  
• Event sourcing backbone  

Krako must NOT:

• Rewrite Task IR semantics  
• Modify escalation graph  
• Increase budgets  
• Invent new reasoning stages  
• Downgrade or upgrade WorkUnit types  

Krako decides WHERE and HOW.

---

# 4. What Must Be Unified (Single Source of Truth)

To prevent duplication, the following must have exactly one authority.

## 4.1 Task IR → WorkUnit Mapping

Single normative mapping table:

TaskIR.type → WorkUnit.kind  
TaskIR.budget → budget fields  
TaskIR.schema → verification rules  
TaskIR.metadata.trace_id → execution_session_id  

This mapping must live in a single Interface Spec document.

---

## 4.2 Budget Invariants

Invariant:

Budget may decrease.  
Budget may never increase.

Enforcement split:

KORA declares budget.  
Krako enforces budget at runtime boundary.

There must be no independent budget logic in fabric.

---

## 4.3 Retry Ownership

Retry decision authority:

KORA defines max_retries.  
Krako executes retry timing/backoff.

Krako may not exceed retry cap.

---

## 4.4 Stage & Event Taxonomy

We must create a single canonical stage mapping table:

KORA Stage → Krako Event Sequence

Example:

DETERMINISTIC → workunit.dispatched + workunit.completed  
ADAPTER → llm.invocation.started  
VERIFY → workunit.completed + validation_status  
BUDGET_BREACH → workunit.failed (reason=BUDGET_BREACH)

Without this mapping, telemetry drift is guaranteed.

---

# 5. KORA Studio Baseline Definition

KORA Studio is the local runtime product.

It must be defined as:

"KORA Control Plane + Minimal Local Execution Engine"

NOT:

• A partial Krako 2.0 clone  
• A billing-enabled distributed fabric  
• A trust-scored node network  

---

## 5.1 KORA Studio Scope

KORA Studio includes:

• Task IR  
• DAG execution  
• Deterministic execution  
• Local reasoning adapter  
• Budget enforcement  
• Schema validation  
• Telemetry export  

Optional (dev mode only):

• Local WorkUnit simulation

Excluded from Studio:

• Node Agent protocol  
• Ledger  
• Trust scoring  
• Autoscaling  
• Admission control  
• Distributed routing

Studio is a single-machine deterministic-first engine.

---

# 6. Preventing Future Drift

To prevent duplication going forward:

## 6.1 Shared Contracts Folder

Create shared spec folder:

/docs/contracts/

Containing:

• task_ir_contract.md  
• kora_krako_interface.md  
• stage_taxonomy.md  
• budget_governance_contract.md  
• determinism_replay_contract.md

These must be treated as immutable unless version incremented.

---

## 6.2 CI Invariant Gates

Minimum CI gates across both repos:

• Telemetry completeness  
• Budget non-increase  
• Schema enforcement  
• No hidden LLM invocation  
• Replay determinism equivalence  

Breaking any invariant fails merge.

---

# 7. Final Strategic Positioning

KORA is the execution intelligence engine.
Krako is the execution fabric.
KORA Studio is the single-node reference runtime.

Flow:

User → KORA (TaskGraph)  
TaskGraph → Krako Fabric (ExecutionSession)  
Krako → Telemetry → Billing/Trust  

KORA Studio = KORA without Fabric.

---

# 8. Immediate Action Plan

1. Freeze responsibility boundary (no drift).  
2. Create final Interface Spec v1.0 (field-level mapping).  
3. Create Stage Taxonomy Alignment Guide.  
4. Create Determinism & Replay Contract.  
5. Define KORA Studio runtime subset spec.  

After this, development may proceed independently without duplication.

---

# Closing Position

KORA governs intelligence.  
Krako governs execution infrastructure.  
Studio governs local discipline.

If boundaries remain clear, duplication disappears.
If boundaries blur, architectural debt begins.

Structure must remain singular at the contract level.
Scale must remain singular at the fabric level.

