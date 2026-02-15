
---

# 📄 3️⃣ `docs/architecture.md`

```markdown
# KORA Architecture

**Version:** v0.1-alpha  
**Date:** March 8, 2025  

---

## Execution Flow

1. User input
2. Task IR generation
3. DAG validation
4. Deterministic execution
5. Budget evaluation
6. Adapter call (if required)
7. Structured verification
8. Retry / fail policy
9. Result aggregation

---

## Design Properties

• Deterministic-first  
• Inference as bounded resource  
• JSON-only structured output  
• Loose coupling via HTTP adapters  
• Failure isolation  

---

## Core Components

- Task IR
- Scheduler (DAG)
- Budget Engine
- Deterministic Executor
- Reasoning Adapter
- Verification Layer
