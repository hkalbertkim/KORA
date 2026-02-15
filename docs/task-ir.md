# Task IR (v0.1-min)

KORA operates on structured tasks, not prompts.

TaskGraph:
- graph_id
- version
- root
- defaults.budget
- tasks[]

Task:
- id
- type
- deps[]
- in
- run (det|llm)
- verify
- policy
- tags

LLM tasks require output_schema.
Graph must be acyclic.
