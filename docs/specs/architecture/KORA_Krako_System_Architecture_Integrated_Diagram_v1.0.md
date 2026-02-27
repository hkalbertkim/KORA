# KORA + KORA Studio + Krako Cloud – Integrated System Architecture Diagram v1.0

Status: Architecture Integration Draft  
Language: English (Official Document)  
Purpose: Provide a single, unambiguous architecture diagram set that explains how KORA, KORA Studio, Krako Contracts, and Krako Cloud work together without dependency confusion.

---

# 1. Canonical Dependency Direction

Dependency must flow in one direction:

KORA (semantic authority)
    ↓
Krako Contracts (public interface)
    ↓
Krako Cloud Fabric (private infrastructure)

KORA Studio runs KORA locally and may optionally use Krako Cloud via a backend plugin.

---

# 2. System Stack Diagram

```mermaid
flowchart TD
  A["Applications"] --> B["KORA (Control Plane / Execution Intelligence)"]
  B --> C["ExecutionBackend Interface"]
  C --> D["LocalBackend (KORA Studio)"]
  C --> E["KrakoBackend Plugin"]
  E --> F["Krako Contracts (Open)" ]
  F --> G["Krako Cloud Fabric (Closed)" ]
```

---

# 3. KORA Studio (Local-Only) Architecture

```mermaid
flowchart TD
  A["Browser UI (Chat)"] --> B["KORA Core"]
  B --> C["Task Construction"]
  C --> D["DAG Validation"]
  D --> E["Deterministic Executor (CPU)"]
  E --> F{"Model Task Required?"}
  F -->|No| G["Aggregation"]
  F -->|Yes| H["Local Reasoning Adapter"]
  H --> I["Local LLM Runtime (Ollama/LM Studio/llama.cpp)"]
  I --> J["Schema Validation"]
  J --> G
  G --> K["Telemetry Bundle (Local)"]
  K --> L["TaskGraph Inspector (Advanced Mode)"]
```

---

# 4. Optional Cloud Execution Path (Studio → Krako Cloud)

```mermaid
flowchart TD
  A["Browser UI (Chat)"] --> B["KORA Core"]
  B --> C["TaskGraph (Immutable)"]
  C --> D["KrakoBackend Plugin"]
  D --> E["Krako Contracts API"]
  E --> F["Krako Gateway"]
  F --> G["ExecutionSession Manager"]
  G --> H["Scheduler"]
  H --> I["CPU Nodes (Node Agents)"]
  H --> J["LLM Pods (GPU)" ]
  I --> K["WorkUnit Results"]
  J --> K
  K --> L["Result Aggregator"]
  L --> M["Event Log (Append-only)"]
  M --> N["Billing Consumer (Ledger)"]
  M --> O["Trust Consumer (Reputation)"]
  M --> P["Autoscaling Controller"]
  L --> Q["ExecutionResult + Telemetry Bundle"]
  Q --> R["KORA Studio UI + Inspector"]
```

---

# 5. Control vs Data Plane Boundary

```mermaid
flowchart LR
  A["KORA Control Plane"] -->|"TaskGraph + Constraints"| B["Krako Data Plane"]
  B -->|"Results + Telemetry"| A

  B --> C["Billing"]
  B --> D["Trust"]
  B --> E["Autoscaling"]

  C -->|"Derived from events"| B
  D -->|"Derived from events"| B
  E -->|"Derived from events"| B
```

Rules:

• KORA owns semantics (what/why).  
• Krako owns execution (where/how).  
• Billing/Trust/Autoscaling consume events asynchronously.  

---

# 6. Contract vs Policy Boundary

```mermaid
flowchart TD
  A["Public Contracts (Open)"] --> B["WorkUnit Schema"]
  A --> C["Event Envelope"]
  A --> D["Stop-Reason Taxonomy"]
  A --> E["Determinism & Replay Guarantees"]
  F["Private Policies (Closed)"] --> G["Scheduler Heuristics"]
  F --> H["Billing Engine Internals"]
  F --> I["Trust Algorithm"]
  F --> J["Autoscaling Tuning"]
```

Public contracts must remain stable and versioned.
Private policies may evolve without breaking contracts.

---

# 7. End-to-End Execution Sequence (High Level)

```mermaid
sequenceDiagram
  participant U as User
  participant UI as KORA Studio UI
  participant K as KORA Core
  participant EB as ExecutionBackend
  participant KB as KrakoBackend (optional)
  participant KC as Krako Cloud

  U->>UI: Submit message
  UI->>K: request
  K->>K: Build TaskGraph
  K->>EB: execute_taskgraph(TaskGraph)

  alt LocalBackend
    EB->>K: ExecutionResult + Telemetry
  else KrakoBackend
    EB->>KB: Submit TaskGraph
    KB->>KC: Execute (ExecutionSession)
    KC->>KB: Results + Events
    KB->>K: ExecutionResult + Telemetry
  end

  K->>UI: Render response + badges
  UI->>U: Display output
```

---

# 8. Summary

This architecture ensures:

• KORA Studio runs fully standalone  
• Krako Cloud is optional and plugin-based  
• Contracts are public, policies are private  
• Semantic authority remains in KORA  
• Scale and monetization remain in Krako Cloud

---

End of Document

