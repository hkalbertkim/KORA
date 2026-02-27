# KORA ↔ Krako Contract Mapping Tables v1.0

Status: Interoperability Lock Specification  
Language: English (Official Document)  
Purpose: Define canonical field-level and semantic mappings between KORA (Control Plane) and Krako (Data Plane) to prevent duplication and semantic drift.

---

# 1. Scope

This document defines:

• Task IR ↔ WorkUnit field mapping  
• TaskGraph ↔ ExecutionSession mapping  
• Stage taxonomy ↔ Event taxonomy mapping  
• Stop-reason ↔ Failure classification mapping  
• Budget & retry enforcement responsibility mapping

This is a normative document.

---

# 2. Task IR → WorkUnit Mapping

## 2.1 Identity Mapping

| KORA Task IR Field | Krako WorkUnit Field | Rule |
|--------------------|----------------------|------|
| id | work_unit_id | 1:1 mapping |
| version | schema_version | Must match contract version |
| type | kind | deterministic → cpu, model → llm_pod, aggregation → cpu |
| dependencies | dependencies | Immutable, DAG preserved |
| metadata.trace_id | execution_session_id | Propagated without modification |

Rule: Krako must not mutate Task IR identity fields.

---

## 2.2 Budget Mapping

| KORA Budget Field | Krako Enforcement Field | Enforcement Location |
|-------------------|--------------------------|----------------------|
| max_tokens | token_cap | LLM invocation boundary |
| max_time_ms | timeout_ms | Executor runtime guard |
| max_retries | retry_cap | Scheduler retry logic |

Invariant:

RemainingBudget_after_execution ≤ DeclaredBudget

Krako must enforce but never increase budgets.

---

## 2.3 Schema & Validation Mapping

| KORA Field | Krako Responsibility |
|------------|---------------------|
| schema | Enforced at execution boundary |
| additionalProperties=false | Must be honored |
| validation_status | Emitted in event telemetry |

Krako must never bypass schema validation.

---

# 3. TaskGraph → ExecutionSession Mapping

| KORA TaskGraph Field | Krako ExecutionSession Field |
|-----------------------|-------------------------------|
| graph_id | execution_session_id |
| root | root_work_unit_id |
| defaults.budget | session_budget |
| tasks[] | work_units[] |

ExecutionSession must preserve TaskGraph immutability.

---

# 4. Stage Taxonomy ↔ Event Taxonomy Mapping

## 4.1 KORA Stage Definitions

• TASK_CONSTRUCTED  
• DAG_VALIDATED  
• DETERMINISTIC_EXECUTION  
• MODEL_INVOCATION  
• SCHEMA_VALIDATION  
• AGGREGATION  
• TASK_COMPLETED  
• TASK_FAILED

## 4.2 Canonical Event Mapping

| KORA Stage | Krako Event Sequence |
|-------------|---------------------|
| DETERMINISTIC_EXECUTION | workunit.started → workunit.completed |
| MODEL_INVOCATION | llm.invocation.started → llm.invocation.completed |
| SCHEMA_VALIDATION | workunit.validated |
| TASK_FAILED | workunit.failed |
| TASK_COMPLETED | workunit.completed (status=success) |

Semantic order must be preserved across backends.

---

# 5. Stop-Reason Mapping

## 5.1 Canonical Stop Reasons (KORA Authority)

• VALIDATION_ERROR  
• TIMEOUT  
• BUDGET_BREACH  
• DEPENDENCY_FAILURE  
• EXECUTION_FAILURE

## 5.2 Krako Event Classification Mapping

| Krako Failure Source | KORA Stop Reason |
|----------------------|------------------|
| Schema mismatch | VALIDATION_ERROR |
| Timeout exceeded | TIMEOUT |
| Token cap exceeded | BUDGET_BREACH |
| Upstream failure | DEPENDENCY_FAILURE |
| Executor error | EXECUTION_FAILURE |

Backends may not introduce new stop reasons without contract version increment.

---

# 6. Retry Responsibility Mapping

| Responsibility | KORA | Krako |
|---------------|-------|--------|
| Define max_retries | Yes | No |
| Execute retry scheduling | No | Yes |
| Enforce retry cap | Yes (declaration) | Yes (execution) |
| Retry backoff algorithm | No | Yes (policy) |

Krako must not exceed declared retry_cap.

---

# 7. Determinism & Replay Mapping

| Guarantee | Responsible Layer |
|-----------|-------------------|
| Deterministic-first rule | KORA |
| Budget non-increase | Krako enforcement |
| Event append-only | Krako |
| Replay-safe ledger | Krako |
| Stage semantic preservation | Both |

Replay invariants:

Given identical TaskGraph + contract version + backend capabilities,
semantic stage sequence must remain equivalent.

---

# 8. Telemetry Field Mapping

| KORA Telemetry Field | Krako Event Field |
|----------------------|--------------------|
| task_id | work_unit_id |
| task_type | kind |
| duration_ms | duration_ms |
| tokens_in | tokens_in |
| tokens_out | tokens_out |
| retry_count | attempt_index |
| validation_status | validation_status |
| total_latency_ms | session_latency_ms |

Cloud-specific telemetry may extend but must not remove core fields.

---

# 9. Forbidden Responsibility Transfers

The following are prohibited:

• Krako redefining Task IR semantics  
• KORA implementing scheduler heuristics  
• Fabric escalating models beyond declared type  
• KORA embedding billing logic  
• Fabric modifying dependency graph

Violation requires architectural review.

---

# 10. Summary

KORA defines structure.
Krako executes structure.
Contracts define mapping.

This document freezes semantic interoperability.

---

End of Document
