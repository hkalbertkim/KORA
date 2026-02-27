# KORA–Krako Contract Versioning & Compatibility Policy v1.0

Status: Governance & Stability Specification  
Language: English (Official Document)  
Purpose: Define versioning rules, compatibility guarantees, and breaking-change policies across KORA, Krako Contracts, and Krako Cloud Fabric.

---

# 1. Scope

This policy governs versioning of:

• Task IR schema  
• TaskGraph structure  
• WorkUnit schema  
• ExecutionSession schema  
• Event envelope format  
• Stop-reason taxonomy  
• Determinism & replay guarantees  
• ExecutionBackend interface

It does NOT govern internal Krako Fabric implementation details.

---

# 2. Versioning Layers

The system consists of three independently versioned layers.

## 2.1 KORA Core

Includes:

• Task IR  
• DAG semantics  
• Budget semantics  
• Schema validation semantics  
• Stage definitions

Version format:

MAJOR.MINOR.PATCH

Example:

1.0.0

---

## 2.2 Krako Contracts

Includes:

• WorkUnit JSON schema  
• ExecutionSession schema  
• Event envelope schema  
• Stop-reason taxonomy  
• Determinism & replay guarantees

Version format:

MAJOR.MINOR.PATCH

This layer is the formal interoperability boundary.

---

## 2.3 Krako Fabric

Fabric versioning is internal.

Fabric may change implementation freely as long as:

• Public contract schemas remain satisfied  
• Determinism guarantees preserved  
• Budget non-increase invariant preserved

Fabric version is not required to match KORA version.

---

# 3. Semantic Versioning Rules

## 3.1 MAJOR Version Increment

Required when:

• Task IR schema changes incompatibly  
• Required fields are added without default  
• Stop-reason taxonomy changes  
• Event envelope structure changes  
• Determinism guarantees change

MAJOR changes require explicit migration documentation.

---

## 3.2 MINOR Version Increment

Allowed when:

• Optional fields added  
• New stop-reason values added (backward-compatible)  
• New telemetry fields added  
• Backward-compatible extensions introduced

MINOR changes must not break existing clients.

---

## 3.3 PATCH Version Increment

Used for:

• Documentation updates  
• Bug fixes  
• Clarifications without semantic change

PATCH changes must not alter behavior.

---

# 4. Compatibility Matrix

KORA ↔ Krako Contracts compatibility must follow:

| KORA Version | Contracts Version | Compatible? |
|--------------|-------------------|-------------|
| 1.x          | 1.x               | Yes         |
| 1.x          | 2.x               | No          |
| 2.x          | 1.x               | No          |

Major versions must match.
Minor and patch versions may differ if backward-compatible.

---

# 5. Version Declaration Requirements

Each TaskGraph must include:

"kora_version": "1.0.0"

Each Contract payload must include:

"contract_version": "1.0.0"

Backends must validate compatibility before execution.

If incompatible:

Return explicit error:

error_type = VERSION_MISMATCH

No silent downgrade or fallback is allowed.

---

# 6. Deprecation Policy

When deprecating a field or behavior:

• Mark as deprecated in documentation  
• Emit telemetry warning for at least one MINOR cycle  
• Provide migration guidance  
• Remove only in next MAJOR release

Silent removal is prohibited.

---

# 7. Determinism Guarantee Preservation

All versions must preserve:

• Deterministic-first rule  
• Budget non-increase invariant  
• Schema validation enforcement  
• No hidden inference rule

If any invariant changes, MAJOR increment required.

---

# 8. Migration Strategy

For MAJOR updates:

1. Publish new version alongside previous version  
2. Provide conversion tools  
3. Maintain dual compatibility window  
4. Collect telemetry on version adoption  
5. Announce removal timeline

Migration must be measurable and reversible.

---

# 9. Testing Requirements

Each version change must include:

• Backward compatibility tests  
• Replay determinism tests  
• Budget enforcement tests  
• Schema validation tests  
• Contract compatibility tests

CI must fail if compatibility rules violated.

---

# 10. Policy Summary

Contracts are versioned strictly.
Fabric evolves independently.
KORA remains semantic authority.

Major versions align semantics.
Minor versions extend safely.
Patch versions clarify without changing behavior.

Versioning protects architectural integrity.

---

End of Document

