# Retrieval Warm Test (2026-02-22)

## Command
`python3 scripts/metrics/run_retrieval_warm_test.py`

## Date/Time
`2026-02-22 20:03:51 CET`

## Printed Metrics (verbatim)
```text
/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/site-packages/pydantic/_internal/_fields.py:198: UserWarning: Field name "schema" in "VerifySpec" shadows an attribute in parent "BaseModel"
  warnings.warn(
N: 50
task_type: llm.answer
input_payload: {'question': 'User asks for a concise summary of cost variance risks in an AI support assistant rollout.'}
baseline enable_gate_retrieval: False
baseline_full_count/N: 50/50
baseline_tail_full_rate: 1.0000
warmed enable_gate_retrieval: True
warmed_full_count/N: 0/50
retrieval_enabled_tail_full_rate: 0.0000
warm_behavior: before each warmed run, retrieval store receives a put() of a known-good full output
```

## Interpretation
Under the same fixed workload and task input, terminal full-stage usage dropped from `50/50 (100%)` in baseline mode to `0/50 (0%)` with warmed gate retrieval enabled, showing that the full tail collapsed from 100% to 0% after warm cache.
