# KORA Public API Specification v1.0

Status: External Interface Specification  
Language: English (Official Document)  
Purpose: Define the public API surface for KORA Studio (local) and Krako Cloud (remote) while preserving architectural boundaries and contract invariants.

---

# 1. Scope

This document defines:

• KORA Studio Local API  
• Krako Cloud Public API  
• Authentication models  
• Request/Response schemas  
• Error handling format  
• Versioning requirements

This document does NOT define internal Fabric APIs.

---

# 2. API Design Principles

All APIs must:

• Be deterministic with explicit contracts  
• Require explicit schema for model-bound tasks  
• Enforce budget constraints  
• Return structured JSON only  
• Never silently downgrade behavior

---

# 3. Versioning

Every API request must include:

"api_version": "1.0"

If incompatible:

Return:

{
  "error_type": "VERSION_MISMATCH",
  "message": "Incompatible API version"
}

---

# 4. KORA Studio Local API

Base URL (default):

http://localhost:{port}

---

## 4.1 POST /execute

Description:
Execute a TaskGraph locally.

Request:

{
  "api_version": "1.0",
  "taskgraph": { ... TaskGraph JSON ... },
  "execution_options": {
    "backend": "local",
    "stream": false
  }
}

Response:

{
  "status": "success | failed",
  "final_output": { ... structured JSON ... },
  "telemetry": { ... telemetry bundle ... },
  "execution_metadata": {
    "run_id": "uuid",
    "backend": "local",
    "duration_ms": 1234
  }
}

---

## 4.2 GET /models

Description:
Return installed local models.

Response:

{
  "models": [
    {
      "model_id": "llama-7b-q4",
      "backend": "ollama",
      "context_tokens": 4096,
      "estimated_vram_mb": 4096
    }
  ]
}

---

## 4.3 GET /health

Description:
Return local runtime health.

Response:

{
  "status": "healthy",
  "cpu_load": 0.32,
  "gpu_available": true,
  "active_sessions": 1
}

---

## 4.4 GET /telemetry/{run_id}

Description:
Retrieve telemetry for specific run.

Response:

{
  "run_id": "uuid",
  "tasks": [ ... ],
  "summary": { ... }
}

---

# 5. Krako Cloud Public API

Base URL:

https://api.krako.ai/v1

Authentication:

• API Key (header: Authorization: Bearer <token>)  
• OAuth2 (future support)

---

## 5.1 POST /execute

Description:
Submit TaskGraph for distributed execution.

Request:

{
  "api_version": "1.0",
  "contract_version": "1.0.0",
  "taskgraph": { ... },
  "execution_options": {
    "priority": "normal",
    "region": "us-east"
  }
}

Response:

{
  "status": "success | failed",
  "execution_session_id": "uuid",
  "final_output": { ... },
  "telemetry": { ... },
  "billing": {
    "tokens_in": 1200,
    "tokens_out": 800,
    "estimated_cost_usd": 0.032
  }
}

---

## 5.2 GET /execution/{execution_session_id}

Description:
Retrieve execution result and telemetry.

Response:

{
  "execution_session_id": "uuid",
  "status": "completed",
  "final_output": { ... },
  "telemetry": { ... }
}

---

## 5.3 GET /billing/usage

Description:
Retrieve billing usage for authenticated tenant.

Response:

{
  "period_start": "YYYY-MM-DD",
  "period_end": "YYYY-MM-DD",
  "total_tokens": 123456,
  "estimated_cost_usd": 42.50
}

---

# 6. Error Handling Standard

All errors must return:

{
  "error_type": "VALIDATION_ERROR | TIMEOUT | BUDGET_BREACH | VERSION_MISMATCH | EXECUTION_FAILURE",
  "message": "Human-readable explanation",
  "details": { ... optional structured info ... }
}

HTTP status codes:

• 400 – Client error (validation, version)  
• 401 – Unauthorized  
• 403 – Forbidden  
• 429 – Rate limited  
• 500 – Internal execution error

---

# 7. Streaming (Future Extension)

Streaming support may be added via:

• SSE (Server-Sent Events)

Streaming must preserve:

• Deterministic stage order  
• Schema enforcement at completion  
• Budget cap enforcement

Streaming is not mandatory for v1.0.

---

# 8. Invariants

The API must guarantee:

• No hidden inference  
• No automatic backend switching  
• Budget enforcement  
• Deterministic-first preservation  
• Contract version validation

---

# Final Position

KORA Studio API enables local structured execution.
Krako Cloud API enables scalable structured execution.

Both share contract semantics.
Only substrate differs.

---

End of Document
