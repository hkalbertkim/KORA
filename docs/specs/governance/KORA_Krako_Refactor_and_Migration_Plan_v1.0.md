# KORA–Krako Refactor & Migration Plan v1.0

Status: Engineering Transition Blueprint  
Language: English (Official Document)  
Purpose: Define the step-by-step refactor plan to move from current mixed implementation to the target 3-layer architecture (KORA / Contracts / Krako Fabric) without duplication or semantic drift.

---

# 1. Objective

Current state:

• KORA and Krako 2.0 developed in parallel  
• Some overlapping semantics exist  
• Retry, budget, and stage logic may be partially duplicated  

Target state:

• KORA = semantic authority  
• Krako Contracts = public interoperability layer  
• Krako Fabric = infrastructure implementation  

No semantic duplication.
No responsibility ambiguity.

---

# 2. Target Repository Structure

Final structure:

1. kora/ (Open)  
2. krako-contracts/ (Open)  
3. krako-fabric/ (Private)

Dependency direction:

kora → krako-contracts → krako-fabric

Never the reverse.

---

# 3. Migration Phases

Migration must be incremental and safe.

---

## Phase 1 – Contract Extraction

Goal:

Extract all shared schemas into krako-contracts.

Actions:

1. Move WorkUnit schema definitions.  
2. Move Event envelope schema.  
3. Move stop-reason taxonomy.  
4. Move ExecutionSession schema.  
5. Add explicit contract_version fields.

Validation:

• CI must pass contract compatibility tests.  
• Fabric must import only from krako-contracts.

No logic changes allowed in this phase.

---

## Phase 2 – Semantic Isolation

Goal:

Ensure semantic authority remains exclusively in KORA.

Actions:

1. Remove any decomposition logic from Krako.  
2. Remove escalation graph logic from Fabric.  
3. Ensure Fabric does not mutate TaskGraph fields.  
4. Verify retry caps defined only in KORA.

Add tests:

• Forbidden responsibility transfer test  
• Deterministic-first conformance test

---

## Phase 3 – Backend Abstraction Enforcement

Goal:

Enforce ExecutionBackend boundary.

Actions:

1. Introduce explicit ExecutionBackend interface in KORA.  
2. Implement LocalBackend (Studio).  
3. Implement KrakoBackend adapter using contract API.  
4. Remove any direct Fabric calls from KORA.

Validation:

• Cross-backend equivalence tests must pass.  
• No circular dependencies allowed.

---

## Phase 4 – Fabric Decoupling

Goal:

Ensure krako-fabric contains only infrastructure logic.

Actions:

1. Remove any semantic decision code from Fabric.  
2. Centralize scheduler heuristics in Fabric only.  
3. Isolate billing engine fully inside Fabric.  
4. Isolate trust scoring fully inside Fabric.

Add static checks:

• Fabric must not import KORA modules.

---

## Phase 5 – Studio Hard Separation

Goal:

Guarantee Studio operates independently.

Actions:

1. Verify Studio runs with LocalBackend only.  
2. Remove any cloud-only assumptions.  
3. Add offline test suite.  
4. Validate no billing/trust code reachable from Studio.

---

# 4. Refactor Checklist

The following checklist must be completed before declaring migration complete:

• All shared schemas moved to krako-contracts.  
• No semantic duplication across repos.  
• All CI conformance tests pass.  
• Versioning policy implemented.  
• ExecutionBackend interface stable.  
• Cross-backend equivalence validated.  
• Replay determinism test validated.  
• Studio runs fully offline.

---

# 5. Risk Mitigation Strategy

Risks:

• Breaking existing integrations  
• Hidden semantic dependencies  
• Replay divergence  
• Version mismatch

Mitigation:

• Dual-support window during MAJOR changes  
• Feature flags for migration  
• Nightly cross-repo integration tests  
• Replay verification before release

---

# 6. Rollback Strategy

Each phase must be reversible.

Rollback method:

• Maintain branch snapshot before refactor phase  
• Feature-flag new boundary enforcement  
• Version gate changes

No irreversible changes until CI fully green.

---

# 7. Timeline Suggestion

Week 1: Contract extraction  
Week 2: Semantic isolation  
Week 3: Backend abstraction enforcement  
Week 4: Fabric decoupling  
Week 5: Studio validation & cleanup

Release after full conformance validation.

---

# 8. Completion Criteria

Migration is complete when:

• KORA repo contains no Fabric logic  
• Fabric repo contains no semantic authority logic  
• Contracts repo contains only schemas & invariants  
• CI enforces boundaries automatically  
• Studio operates independently  

---

# Final Position

Refactoring is not code movement.
It is boundary enforcement.

After migration:

Structure = Open  
Contracts = Stable  
Scale = Private  

Architectural clarity becomes permanent.

---

End of Document

