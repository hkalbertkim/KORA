# KORA ExecutionBackend Interface Contract v1.0

Status: Technical Boundary Specification  
Language: English (Official Document)  
Purpose: Define the formal interface between KORA (Control Plane / Studio) and any execution backend (Local or Krako Cloud), ensuring zero duplication and strict boundary enforcement.

---

# 1. Architectural Role

ExecutionBackend is an abstraction layer.

It allows KORA to:

• Execute TaskGraphs locally  
• Execute TaskGraphs via Krako Cloud  
• Switch backends without modifying core logic  

ExecutionBackend must NEVER contain:

• Task decomposition logic  
• Escalation graph logic  
• Budget declaration logic  
• Schema definition logic  

Those belong exclusively to KORA.

---

# 2. Design Goals

The interface must guarantee:

• Determinism preservation  
• Budget non-increase invariant  
• Retry cap enforcement  
• Schema validation enforcement  
• Telemetry completeness  

Backends differ in scale, not semantics.

---

# 3. Interface Definition (Conceptual API)

ExecutionBackend MUST implement the following methods.

## 3.1 execute_taskgraph

Signature (conceptual):

execute_taskgraph(
    taskgraph: TaskGraph,
    execution_context: ExecutionContext
) -> ExecutionResult

Where:

TaskGraph:
• Fully constructed by KORA  
• Immutable once passed to backend  

ExecutionContext includes:
• run_id  
• trace_id  
• backend_mode (local | krako)  
• user_id (optional)  

ExecutionResult includes:
• final_output  
• telemetry_bundle  
• execution_metadata  

---

## 3.2 health_check

health_check() -> BackendStatus

Returns:

• status (healthy | degraded | unavailable)  
• capacity_summary  
• backend_version

Studio uses this to determine upgrade suggestions.

---

## 3.3 capability_descriptor

capability_descriptor() -> BackendCapabilities

Includes:

• max_model_size  
• max_concurrency  
• supported_task_types  
• supported_context_window  
• distributed (true/false)

KORA must not infer capabilities beyond this descriptor.

---

# 4. LocalBackend Specification

LocalBackend must:

• Execute deterministic tasks locally  
• Invoke local model adapter for model tasks  
• Enforce budgets strictly  
• Perform schema validation locally  
• Emit full telemetry bundle

LocalBackend must not:

• Use distributed scheduling  
• Persist billing ledger  
• Implement trust scoring  
• Modify taskgraph semantics

---

# 5. KrakoBackend Specification

KrakoBackend must:

• Submit TaskGraph via Krako Contract API  
• Receive ExecutionSession result  
• Return structured ExecutionResult  
• Map Krako events into KORA telemetry format

KrakoBackend must not:

• Modify Task IR fields  
• Increase budgets  
• Rewrite escalation logic  

All semantic decisions remain in KORA.

---

# 6. Determinism Guarantee

Given identical:

• TaskGraph  
• ExecutionContext  
• BackendCapabilities snapshot

The sequence of task stages must remain semantically equivalent across backends.

Note:
Timing and node placement may differ.
Semantic stage order must not.

---

# 7. Budget Invariant

Invariant:

RemainingBudget_after_execution ≤ DeclaredBudget

Backend must:

• Enforce token caps  
• Enforce retry caps  
• Enforce timeout limits  

If breach occurs:

Return explicit error:
• error_type = BUDGET_BREACH

No silent overflow.

---

# 8. Telemetry Contract

ExecutionResult.telemetry_bundle must include:

Per-task:
• task_id  
• task_type  
• status  
• duration_ms  
• tokens_in  
• tokens_out  
• retry_count  
• validation_status  

Global:
• total_tokens  
• total_latency_ms  
• model_invocation_count  
• deterministic_task_count  

Cloud-specific fields (optional):
• execution_session_id  
• region  
• billing_id

---

# 9. Failure Handling Contract

ExecutionResult must classify failures as:

• VALIDATION_ERROR  
• TIMEOUT  
• BUDGET_BREACH  
• DEPENDENCY_FAILURE  
• EXECUTION_FAILURE

Backends may not introduce new failure categories without version increment.

---

# 10. Versioning

ExecutionBackend interface version must be explicitly declared.

Breaking changes require:

• MAJOR version increment  
• Compatibility mapping defined  

Backends must refuse execution if incompatible.

---

# 11. Security Constraints

Backend must:

• Never expose raw model invocation without schema validation  
• Never bypass deterministic-first rule  
• Never escalate models beyond declared constraints

All cloud communications must be encrypted.

---

# 12. Extension Model

Future extensions may include:

• Streaming execution support  
• Partial graph execution  
• Multi-region execution hints  

Extensions must preserve core invariants.

---

# Final Position

ExecutionBackend is a scale adapter.
It is not an intelligence layer.

KORA defines structure.
Backends provide execution substrate.

Semantic authority remains in KORA.

---

End of Document

