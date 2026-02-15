# Reasoning Adapter

Adapters isolate model dependencies.

Contract:

Request:
- task_id
- input
- budget
- output_schema

Response:
- ok
- output (JSON only)
- usage
- meta

Adapters are replaceable.
KORA remains model-agnostic.
