# Krako–KORA Interface Specification v1.0 (Draft)

Status: Draft
Owner: Krako Core / KORA Core
Purpose: Define formal interface contract between KORA (Control Plane) and Krako 2.0 (Data Plane)

---

# 0. Scope

This document specifies the executable contract between:

- KORA (Deterministic TaskGraph producer)
- Krako 2.0 (Distributed execution fabric)

It defines:

- Payload schema contract
- Entity mapping tables
- Escalation semantics mapping
- Budget enforcement rules
- Event emission contract
- Failure and stop_reason taxonomy
- Version compatibility rules

This document is normative. Boundary Definition v1.0 defines responsibility separation; this document defines runtime interoperability.

---

# 1. Ingress Contract (TaskGraph Submission)

## 1.1 Submission Surface

KORA submits a TaskGraph JSON payload to Krako via:

- HTTP/gRPC endpoint
- Internal runtime adapter
- Future: message bus submission

Krako MUST validate before ExecutionSession creation.

---

## 1.2 Required TaskGraph Fields

| Field | Type | Required | Notes |
|--------|------|----------|-------|
| schema_version | string | YES | Versioned by KORA |
| graph_id | string | YES | Globally unique |
| request_id | string | YES | Idempotency anchor |
| tenant_id | string | YES | Billing scope |
| created_at | timestamp | YES | UTC |
| budgets | object | YES | See 4.0 |
| work_units | array | YES | Non-empty |

Krako MUST reject if:

- DAG contains cycle
- Duplicate work_unit IDs
- Negative budgets
- Unknown schema_version

---

# 2. Entity Mapping Tables

## 2.1 TaskGraph → ExecutionSession

| KORA | Krako | Rule |
|-------|--------|------|
| graph_id | ExecutionSession.graph_id | 1:1 mapping |
| request_id | ExecutionSession.request_id | Immutable |
| tenant_id | ExecutionSession.tenant_id | Billing anchor |
| created_at | ExecutionSession.created_at | Immutable |

One accepted TaskGraph MUST create exactly one ExecutionSession.

---

## 2.2 WorkUnit → WorkUnitExecution

| KORA WorkUnit Field | Krako Field | Enforcement |
|----------------------|--------------|-------------|
| id | work_unit_id | Immutable |
| type | substrate_constraint | cpu / llm_pod enforced |
| dependencies | readiness_gate | Strict gating |
| retries.max_attempts | retry_policy.max_attempts | Cannot exceed |
| retries.backoff_ms | retry_policy.backoff_ms | Exact copy |
| constraints.local_only | placement.local_only | Enforced |
| criticality | execution_priority | Advisory only |

Krako MUST NOT mutate WorkUnit type.

---

# 3. Escalation Semantics

## 3.1 Escalation Ownership

Escalation graph is defined exclusively by KORA in TaskGraph.

Krako MUST:

- Execute escalation path as declared
- Never invent new escalation nodes
- Never escalate outside declared graph

---

## 3.2 Escalation Triggers

KORA may encode escalation edges with conditions such as:

- failure
- schema_mismatch
- confidence_below_threshold
- budget_remaining

Krako evaluates runtime condition and activates declared edge only.

---

# 4. Budget Contract

## 4.1 Budget Fields

| Budget Field | Meaning |
|--------------|---------|
| max_llm_calls | Upper bound LLM invocations |
| max_cpu_units | Upper bound CPU work units |
| max_tokens | Token ceiling |
| max_latency_ms | SLA target |

---

## 4.2 Budget Invariants

Krako MUST enforce:

- Budget non-increase invariant
- Hard stop if budget exhausted
- Retry within declared limits only

Krako MAY reject TaskGraph early if impossible to satisfy.

---

# 5. Event Emission Contract

Krako MUST emit append-only canonical events.

## 5.1 WorkUnit Events

- workunit.scheduled
- workunit.claimed
- workunit.started
- workunit.completed
- workunit.failed

## 5.2 LLM Invocation Events

- llm.invocation.started
- llm.invocation.completed
- llm.invocation.failed

## 5.3 Session Events

- execution.session.started
- execution.session.completed
- execution.session.failed

All events MUST contain:

- event_id (globally unique)
- graph_id
- work_unit_id (nullable for session events)
- timestamp (UTC)
- attempt_index

---

# 6. Stop Reason Taxonomy

Krako MUST standardize stop_reason values.

## 6.1 Allowed stop_reason Values

- success
- retry_exhausted
- dependency_failed
- budget_exhausted
- substrate_failure
- admission_rejected
- validation_failed

No free-form stop_reason allowed.

---

# 7. Determinism Requirements

Given identical:

- TaskGraph
- NodeRegistry state
- Capacity state

Scheduling decision for tie cases MUST be deterministic.

Replay of identical event stream MUST reproduce identical ledger outputs.

---

# 8. Version Compatibility

- schema_version controlled by KORA
- Krako MUST declare supported versions
- Breaking changes require major version increment
- Minor changes MUST be backward compatible

---

# 9. Rejection Conditions

Krako MUST reject TaskGraph if:

- Invalid DAG
- Unknown WorkUnit type
- Unsupported schema_version
- Missing mandatory fields
- Budget fields malformed

Rejection MUST emit validation_failed event.

---

# 10. Conformance Validation (Preview)

Future Conformance Spec will test:

- Deterministic replay
- Budget enforcement
- Escalation correctness
- No duplicate billing
- Telemetry completeness

---

End of Document

