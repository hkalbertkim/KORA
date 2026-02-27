# Repository Structure & Dependency Strategy

Status: Structural Freeze Draft v1.0  
Purpose: Define repository layout, dependency direction, and packaging strategy to prevent duplication and architectural drift between KORA, KORA Studio, and Krako 2.0.

---

# 1. Core Principle

Dependency must flow in ONE direction only:

KORA (Execution Intelligence, Open)
        ↓
Krako Contracts (Open Interface Layer)
        ↓
Krako Fabric (Closed Infrastructure)

Never the reverse.

---

# 2. Recommended Repository Structure

## 2.1 Repo 1 — kora/
(Open Source)

Contains:

• Task IR implementation  
• DAG execution engine  
• Budget governance  
• Schema validation  
• Reasoning adapter abstraction  
• Telemetry model  
• Benchmark harness  
• KORA Studio runtime  

Must NOT contain:

• Distributed scheduler  
• Billing ledger  
• Trust scoring  
• Autoscaling logic  
• Admission control  

KORA must compile and run independently.

---

## 2.2 Repo 2 — krako-contracts/
(Open Source)

Contains:

• WorkUnit schema  
• TaskGraph ingestion API spec  
• ExecutionSession schema  
• Event envelope definition  
• Stop-reason taxonomy  
• Determinism & replay guarantees  
• Budget non-increase invariant definition  

This repo defines the contract between KORA and Krako Fabric.

It must remain stable and versioned.

---

## 2.3 Repo 3 — krako-fabric/
(Closed / Private)

Contains:

• Scheduler heuristics  
• Placement scoring  
• Autoscaling controller  
• Billing engine  
• Ledger reconciliation  
• Trust scoring implementation  
• Admission control  
• Capacity orchestration  
• Pod infrastructure management  

This repo depends on:

• krako-contracts

It must NOT depend on internal KORA code.

---

# 3. Dependency Graph

Visual model:

Application
   ↓
KORA
   ↓
Krako Contracts
   ↓
Krako Fabric

Import rules:

• KORA imports nothing from Fabric  
• Fabric imports Contracts only  
• Contracts import nothing from Fabric  

This prevents circular drift.

---

# 4. Packaging Strategy

## 4.1 KORA Studio Distribution

Package:

kora + studio UI + LocalBackend

No Fabric dependency.

Optional plugin system:

ExecutionBackend interface:

• LocalBackend (default)
• KrakoBackend (optional extension)

KrakoBackend implemented in separate pip package:

krako-backend-client

Installed only when user upgrades.

---

# 5. Version Alignment Policy

Each repo must version independently.

| Layer | Versioning | Breaking Change Policy |
|--------|------------|------------------------|
| KORA | Semantic | Major if Task IR changes |
| Contracts | Strict Semantic | Major if schema changes |
| Fabric | Internal | May change freely if contract preserved |

Contract version mismatch must result in explicit failure.

---

# 6. Upgrade Path (User Perspective)

Stage 1:
User installs KORA Studio (local only).

Stage 2:
User enables Krako Cloud backend.

Studio config adds:

execution_backend = "krako"

Stage 3:
Requests exceeding local capacity automatically route via Contract layer.

No core logic duplication occurs.

---

# 7. Drift Prevention Rules

1. No business logic duplication across repos.  
2. No retry policy in KORA beyond retry caps.  
3. No escalation logic inside Fabric.  
4. No billing logic inside KORA.  
5. All cross-layer communication must use Contract schemas.  

Violation of any rule requires architectural review.

---

# 8. Strategic Benefit

This structure provides:

• Clean open-source surface  
• Clear monetization boundary  
• Studio independence  
• Zero duplication risk  
• Scalable infrastructure layer  
• Long-term architectural clarity  

---

# Closing Statement

KORA defines intelligence.
Contracts define interoperability.
Krako Fabric defines scale.

Structure is public.
Scale is proprietary.

