# KORA–Krako Conformance & CI Gate Specification v1.0

Status: Enforcement & Verification Specification  
Language: English (Official Document)  
Purpose: Define automated conformance tests and CI gates that enforce architectural invariants between KORA, Krako Contracts, and Krako Fabric.

---

# 1. Objective

This specification converts architectural boundaries into executable guarantees.

Documentation alone does not prevent drift.
CI gates must fail when invariants are violated.

This document defines:

• Required invariant tests  
• Cross-layer conformance checks  
• Replay determinism validation  
• Budget non-increase enforcement tests  
• Telemetry completeness verification  
• Forbidden responsibility detection

---

# 2. CI Structure

CI must run at three levels:

1. KORA Repository CI  
2. Krako Contracts Repository CI  
3. Krako Fabric Repository CI  

Cross-repo integration tests must run nightly or pre-release.

---

# 3. Core Architectural Invariants (Must Never Break)

The following invariants are non-negotiable:

• Deterministic-first execution  
• Budget non-increase rule  
• Retry cap enforcement  
• Schema validation mandatory  
• No hidden model invocation  
• Immutable TaskGraph structure  
• Contract version compatibility

CI must fail if any invariant is violated.

---

# 4. Budget Non-Increase Test

## 4.1 Purpose

Ensure remaining budget never exceeds declared budget.

## 4.2 Test Procedure

1. Create TaskGraph with known max_tokens and max_retries.  
2. Execute via LocalBackend.  
3. Execute via KrakoBackend.  
4. Inspect telemetry_bundle.

Assertion:

remaining_tokens <= max_tokens
retry_count <= max_retries

Failure condition:

Any observed value exceeding declared cap.

---

# 5. Deterministic-First Test

## 5.1 Purpose

Ensure deterministic tasks never invoke model layer.

## 5.2 Test Procedure

1. Create TaskGraph containing only deterministic tasks.  
2. Execute locally and via KrakoBackend.  
3. Inspect telemetry.

Assertion:

model_invocation_count == 0

Failure condition:

Any LLM invocation detected.

---

# 6. Schema Enforcement Test

## 6.1 Purpose

Ensure model outputs failing schema validation are rejected.

## 6.2 Test Procedure

1. Provide malformed model response via mock adapter.  
2. Execute TaskGraph.  
3. Capture failure classification.

Assertion:

stop_reason == VALIDATION_ERROR
validation_status == fail

Failure condition:

Malformed output accepted.

---

# 7. Retry Cap Enforcement Test

## 7.1 Purpose

Ensure retry attempts do not exceed declared max_retries.

## 7.2 Test Procedure

1. Use adapter that intentionally fails validation repeatedly.  
2. Set max_retries = 2.  
3. Execute TaskGraph.

Assertion:

retry_count <= 2

Failure condition:

retry_count > max_retries.

---

# 8. Replay Determinism Test

## 8.1 Purpose

Ensure replaying identical event stream yields identical semantic result.

## 8.2 Test Procedure

1. Execute TaskGraph via KrakoBackend.  
2. Capture event log snapshot.  
3. Replay event log into clean environment.  
4. Compare ExecutionResult.

Assertions:

• Final output identical  
• Stage sequence identical  
• Billing totals identical  
• Stop-reason identical

Failure condition:

Any semantic divergence.

---

# 9. Telemetry Completeness Test

## 9.1 Purpose

Ensure every task emits required telemetry fields.

## 9.2 Required Fields

Per-task:

• task_id  
• task_type  
• duration_ms  
• status  
• retry_count  
• validation_status

Global:

• total_latency_ms  
• total_tokens  
• model_invocation_count

Failure condition:

Any required field missing.

---

# 10. Contract Version Compatibility Test

## 10.1 Purpose

Ensure incompatible versions fail fast.

## 10.2 Test Procedure

1. Attempt execution with mismatched MAJOR versions.  
2. Observe returned error.

Assertion:

error_type == VERSION_MISMATCH

Failure condition:

Execution proceeds or silently downgrades.

---

# 11. Forbidden Responsibility Transfer Test

## 11.1 Static Checks

Ensure:

• KORA does not import krako-fabric modules.  
• Krako Fabric does not import KORA internals.

Automated via dependency graph linting.

## 11.2 Dynamic Checks

Ensure:

• Fabric does not modify TaskGraph fields.  
• KORA does not perform scheduling logic.

Failure triggers architectural review.

---

# 12. Cross-Backend Equivalence Test

Execute same TaskGraph via:

• LocalBackend  
• KrakoBackend

Assertions:

• Same semantic stage sequence  
• Same stop-reason  
• Same schema validation outcome  

Allowable differences:

• Latency  
• Node placement  
• Billing metadata

---

# 13. Performance Regression Guard

CI must track:

• model_invocation_count trend  
• retry amplification trend  
• deterministic coverage ratio

If regression exceeds threshold:

Require review.

---

# 14. CI Enforcement Policy

A merge must be blocked if:

• Any invariant test fails  
• Contract compatibility test fails  
• Replay test fails  
• Dependency lint fails

Architectural review required before override.

---

# 15. Summary

CI is the enforcement mechanism of architecture.

KORA defines semantics.
Contracts define interoperability.
Krako Fabric executes policy.

CI guarantees boundaries remain intact.

---

End of Document

