# Gate Retrieval Real Benchmark (2026-02-22)

Command:

```bash
python3 scripts/metrics/benchmark_gate_retrieval_real.py
```

N per scenario per mode: 10

Scenarios:
- exact_repeat: same question repeated
- minor_variations: deterministic rephrasings
- mixed: 50% exact repeat + 50% varied prompts

| scenario | mode | n | terminal_full_rate | retrieval_hit_rate | mean_time_ms | p95_time_ms | mean_tokens_out |
|---|---:|---:|---:|---:|---:|---:|---:|
| exact_repeat | baseline | 10 | 100.00% | 0.00% | 3315.0 | 3828.0 | 132.1 |
| exact_repeat | retrieval | 10 | 10.00% | 90.00% | 1750.5 | 2877.0 | 70.7 |
| minor_variations | baseline | 10 | 100.00% | 0.00% | 4071.6 | 5085.0 | 204.5 |
| minor_variations | retrieval | 10 | 100.00% | 0.00% | 4553.6 | 7155.0 | 223.6 |
| mixed | baseline | 10 | 100.00% | 0.00% | 3597.2 | 4878.0 | 143.4 |
| mixed | retrieval | 10 | 60.00% | 40.00% | 2886.0 | 4303.0 | 131.4 |

## What To Claim
Gate retrieval materially reduced terminal-full executions in exact-repeat traffic while preserving real adapter behavior end-to-end. Benefits were strongest when prompts matched cached keys exactly; minor wording changes reduced hit rate as expected for exact-key retrieval.
