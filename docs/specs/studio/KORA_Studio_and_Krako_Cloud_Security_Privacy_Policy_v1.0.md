# KORA Studio & Krako Cloud Security and Privacy Policy v1.0

Status: Policy Specification  
Language: English (Official Document)  
Purpose: Define security boundaries, privacy defaults, data handling rules, consent requirements, and retention policies for KORA Studio (local) and Krako Cloud (remote).

---

# 1. Core Principles

1. Local-first by default.  
2. No silent data exfiltration.  
3. Explicit consent for cloud execution.  
4. Minimal data retention.  
5. Execution transparency is mandatory.

---

# 2. Definitions

• Local Execution: TaskGraph executed entirely on the user’s machine.  
• Cloud Execution: Any TaskGraph or WorkUnit routed to Krako Cloud infrastructure.  
• Telemetry: Structured execution events and metrics.  
• Content Data: User prompts, context packs, intermediate outputs, model outputs.  
• Identifiers: run_id, trace_id, execution_session_id, tenant_id.

---

# 3. KORA Studio Security Model (Local)

## 3.1 Default Data Boundary

By default, KORA Studio:

• Does not transmit prompts, outputs, or telemetry externally.  
• Stores telemetry locally only.  
• Executes using local CPU/GPU and local model backends.

## 3.2 Local Storage

Local storage includes:

• configs/  
• telemetry/  
• logs/  
• exports/

No local content is uploaded automatically.

## 3.3 Model Backend Connectors

Studio may connect to local inference backends.

Connector security requirements:

• Use localhost-only APIs when possible.  
• Never forward user content to remote endpoints without user action.  
• Health checks must not include user content.

---

# 4. Krako Cloud Security Model (Remote)

## 4.1 Network Security

Cloud execution requires:

• TLS encryption in transit  
• Authentication (session token or API key)  
• Request signing (optional but recommended)

## 4.2 Tenant Isolation

Krako Cloud must enforce tenant isolation:

• tenant_id scoping on execution sessions  
• no cross-tenant memory reuse  
• no cross-tenant prompt cache

---

# 5. Consent Requirements

## 5.1 First Cloud Run Consent

Before the first Cloud Execution, Studio must present:

• What data is transmitted (content + telemetry)  
• What is retained and for how long  
• What is not retained  
• How billing is computed

User must explicitly accept.

No consent, no cloud execution.

## 5.2 Per-Run Visibility

Every cloud-executed response must display:

• Cloud execution badge  
• Region (optional)  
• Cost estimate and billed amount

---

# 6. Data Handling Policy

## 6.1 Data Classification

Data types:

A) Content Data  
B) Telemetry Data  
C) Billing Data  
D) Trust/Reputation Signals

## 6.2 Studio Handling

Studio:

• Stores Content Data in conversation history (local).  
• Stores Telemetry Data locally.  
• Does not store Billing Data unless Cloud is used.

## 6.3 Cloud Handling

Cloud must minimize content retention.

Required for execution:

• prompt  
• context_pack  
• task outputs  

Policy:

• Content Data is retained only as long as needed to complete execution.  
• Telemetry Data is retained for auditing and debugging subject to retention policy.  
• Billing Data is retained for financial audit requirements.

---

# 7. Retention Policy

## 7.1 Studio

Studio retention is user-controlled.

Default:

• Conversation history retained locally until user deletes.

## 7.2 Cloud

Cloud retention defaults:

• Content Data: transient only (execution-time).  
• Telemetry Data: 30 days (default).  
• Billing Ledger Data: 7 years (or required by jurisdiction).  
• Trust Signals: 90 days rolling window.

Retention values must be configurable for enterprise deployments.

---

# 8. Telemetry Privacy

Telemetry must avoid storing sensitive raw content by default.

Telemetry should contain:

• identifiers  
• task types  
• durations  
• token counts  
• stop reasons

If content logging is enabled (debug mode):

• Must be explicit opt-in.  
• Must display warning.  
• Must support immediate disable.

---

# 9. Security Events and Auditing

Cloud must log security-relevant events:

• authentication failures  
• repeated budget breaches  
• retry amplification anomalies  
• suspicious node behaviors

Audit logs must be:

• append-only  
• access-controlled  
• available for enterprise audit

---

# 10. Incident Response

Minimum incident response obligations:

• detect breach  
• isolate affected tenants  
• notify affected users within policy timelines  
• provide mitigation guidance

This document does not define legal timelines.

---

# 11. User Controls

Studio must provide:

• clear toggle for cloud backend enable/disable  
• clear toggle for telemetry sharing (opt-in)  
• clear method to delete local data

Cloud must provide:

• billing portal access  
• ability to revoke API keys  
• account suspension mechanisms

---

# 12. Non-Negotiable Constraints

• No cloud execution without consent.  
• No hidden backend switching.  
• No silent content retention expansion.  
• No cross-tenant memory reuse.  

Violations require immediate remediation.

---

# Final Position

KORA Studio is local-first and private by default.
Krako Cloud is optional scale with explicit consent.

Security is structural.
Privacy is enforced by default.

---

End of Document
