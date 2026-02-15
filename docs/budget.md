# Budget Engine

Inference is bounded by:

- max_time_ms
- max_tokens
- max_retries

Each LLM call must satisfy budget constraints.
Failures trigger retry or fail policy.

Telemetry logs:
- task_id
- attempt
- status
- tokens
- latency
