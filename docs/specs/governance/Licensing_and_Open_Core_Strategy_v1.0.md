# Licensing & Open-Core Strategy

Status: Strategic Monetization Draft v1.0  
Purpose: Define licensing model for KORA (open), Krako Contracts (open), and Krako Fabric (closed) while preserving architectural boundaries and monetization clarity.

---

# 1. Strategic Objective

We must satisfy three constraints simultaneously:

1. Encourage adoption of KORA as execution standard.  
2. Protect Krako Fabric as monetizable infrastructure.  
3. Prevent competitive cloning of the full stack.

Licensing must reinforce architectural boundaries.

---

# 2. Layered Licensing Model

## 2.1 KORA (Fully Open Source)

Recommended License: **Apache 2.0**

Why:

• Permissive → encourages adoption  
• Enterprise-friendly  
• Allows integration into commercial systems  
• Supports ecosystem growth  

KORA becomes the public execution standard.

---

## 2.2 Krako Contracts Layer (Open)

Recommended License: **Apache 2.0**

Reason:

• Contracts must be transparent  
• Encourages ecosystem integrations  
• Does not expose proprietary infrastructure logic  

This prevents vendor lock-in accusations while protecting implementation details.

---

## 2.3 Krako Fabric (Closed Core)

Recommended Model: **Proprietary / Closed Source**

Includes:

• Scheduler heuristics  
• Autoscaling logic  
• Billing engine  
• Trust scoring internals  
• Ledger reconciliation  
• Capacity orchestration  

Revenue Model:

• Cloud subscription  
• Usage-based billing  
• Enterprise deployment licensing  

---

# 3. Alternative Licensing Models (Rejected)

## 3.1 AGPL for KORA

Rejected because:

• Discourages enterprise adoption  
• Conflicts with Studio distribution goals  
• Reduces ecosystem growth  

---

## 3.2 Open-Core Hybrid in Single Repo

Rejected because:

• Blurs architectural boundary  
• Increases duplication risk  
• Makes separation harder over time  

---

# 4. Open-Core Monetization Strategy

The monetization is not in KORA.
The monetization is in scale.

Free Tier:

• KORA Studio (local)  
• Single-node execution  
• Local LLM support  

Paid Tier (Krako Cloud):

• Multi-node scaling  
• High-performance LLM Pods  
• Autoscaling  
• High concurrency  
• Enterprise telemetry & SLA  

This aligns cost with infrastructure consumption.

---

# 5. Defensive Strategy Against Forking

Even if someone forks KORA:

They must build:

• Distributed scheduler  
• Autoscaling controller  
• Trust scoring system  
• Billing ledger  
• Pod orchestration layer  

This is non-trivial and infrastructure-heavy.

KORA being open does not endanger Fabric advantage.

---

# 6. Brand & Trademark Protection

Important:

• KORA name may remain open.  
• "Krako" should be trademark protected.  
• Fabric implementation should not be redistributable under same name.  

This prevents brand confusion.

---

# 7. KORA Studio Distribution Model

Distribution:

• Open GitHub repo  
• Prebuilt binaries  
• Local installer (Mac / Windows / Linux)  

Optional plugin:

• krako-backend-client (connect to cloud)

This preserves independence.

---

# 8. Long-Term Licensing Evolution

If needed later:

• Offer enterprise on-prem Fabric under commercial license  
• Offer usage-based cloud pricing  
• Offer private SLA deployment  

Core remains:

KORA = Open  
Contracts = Open  
Fabric = Proprietary

---

# 9. Final Model Summary

| Layer | License | Revenue Source |
|--------|----------|---------------|
| KORA | Apache 2.0 | None (ecosystem driver) |
| Krako Contracts | Apache 2.0 | None (standard layer) |
| Krako Fabric | Proprietary | Cloud / Enterprise |

---

# Closing Position

Open structure builds ecosystem.
Closed scale builds business.

KORA wins adoption.
Krako wins infrastructure.

Licensing must reinforce architecture, not fight it.