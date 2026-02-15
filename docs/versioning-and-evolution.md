# Versioning and Evolution

KORA is an architectural system.

Architectural systems degrade without disciplined evolution.
<br>This document defines how KORA changes without losing structure.

---

## 1. Versioning Scope

Versioning applies to:

- Task IR schema
- Execution engine behavior
- Routing policy semantics
- Budget enforcement rules
- Validation constraints
- Distributed protocol definitions

Versioning is structural, not cosmetic.

---

## 2. Task IR Versioning

Each Task IR object contains:

```json
{
  "version": "1.0"
}
```

### Rules

- Minor versions must preserve backward compatibility.
- Major versions may introduce structural changes.
- Execution engine must validate compatibility before execution.

A Task IR version mismatch must result in explicit failure, not silent fallback.

---

## 3. Semantic Versioning

KORA follows semantic versioning:

| Type | Meaning |
|-------|----------|
| MAJOR | Breaking structural changes |
| MINOR | Backward-compatible structural additions |
| PATCH | Bug fixes without semantic change |

Structural invariants must not change silently in minor releases.

---

## 4. Backward Compatibility Policy

Backward compatibility must preserve:

- Deterministic-first execution
- Budget enforcement
- Schema validation
- Task atomicity
- Routing neutrality

Changes that weaken these require MAJOR version increment.

---

## 5. Deprecation Policy

Deprecated features must:

- Be documented explicitly
- Emit warning telemetry
- Remain functional for defined transition window
- Have defined removal timeline

Silent removal is prohibited.

Deprecation must not weaken invariants.

---

## 6. Experimental Features

Experimental features must:

- Be isolated behind feature flags
- Not alter default structural behavior
- Emit explicit experimental telemetry
- Be removable without breaking core invariants

Experimental routing, DNFM integration, or distributed features must not destabilize core execution.

---

## 7. Migration Strategy

For structural changes:

1. Introduce new version in parallel.
2. Provide migration tooling.
3. Maintain compatibility window.
4. Collect telemetry on adoption.
5. Remove deprecated version only after validation.

Migration must be measurable.

---

## 8. Evolution Constraints

Evolution must never:

- Reintroduce inference reflexivity.
- Remove budget enforcement.
- Loosen schema validation.
- Collapse task boundaries.
- Hard-code vendor dependencies.

If evolution requires relaxing an invariant, the architecture must be re-evaluated, not patched.

---

## 9. Distributed Protocol Evolution

Distributed execution protocol changes must:

- Maintain message compatibility for one major cycle.
- Preserve Task IR schema integrity.
- Not allow node-level budget escalation.
- Maintain orchestrator authority.

Protocol drift introduces fragmentation.

Fragmentation weakens structure.

---

## 10. Telemetry Compatibility

Telemetry schema must:

- Be versioned.
- Maintain backward-compatible fields where possible.
- Preserve core metrics.

Observability must survive evolution.

---

## 11. Architectural Review Requirement

Any MAJOR version proposal must include:

- Invariant impact analysis
- Performance model impact analysis
- Break-even re-evaluation
- Falsifiability implications

Major changes require structural justification.

---

## 12. Evolution Philosophy

KORA evolves cautiously.
<br>Speed of feature addition is secondary to preservation of structure.
<br>Architecture degrades through convenience.

Governed evolution prevents erosion.

---

## Closing Position

Versioning is not about release notes.

It is about protecting invariants.
<br>Structure must survive change.

**Evolution must respect architecture.**
