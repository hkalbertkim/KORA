# Stress Testing Harness

The stress harness runs a production-style sequence of KORA executions and writes aggregate reports.

## Run

```bash
python3 examples/stress_test/run.py --n 1000 --mix 0.8 --seed 42
```

Optional flags:

- `--n`: number of sequential runs (default `1000`)
- `--mix`: trivial workload ratio (default `0.8`)
- `--seed`: RNG seed for repeatability
- `--exhaust-n`: number of budget exhaustion runs (default: `min(50, max(1, int(n * 0.05)))`)
- `--use-openai` / `--no-use-openai`: prefer OpenAI; automatically falls back to mock when key is missing
- `--out`: report base path (default `docs/reports/stress_report`)

## Covered Scenarios

- 1000 sequential requests (configurable)
- Mixed workload:
  - trivial path (`classify_simple` + `skip_if` => LLM skipped)
  - complex path (LLM execution path)
- Budget exhaustion cohort with extreme budget settings and intentional validation failure capture
  - default size scales with `n` using `min(50, max(1, int(n * 0.05)))`

## Report Contents

The harness writes:

- `docs/reports/stress_report.json`
- `docs/reports/stress_report.md`

Reports include:

- total runs, successes, failures, skipped-LLM runs
- total LLM calls and token totals
- latency percentiles (`p50`, `p95`, `p99`)
- aggregated `stage_counts`
- aggregated `error_type_counts`
- budget breach and escalation-required counters

## Sample Output (2026-02-17)

Run command:

```bash
python3 examples/stress_test/run.py --n 1000 --mix 0.8 --seed 42
```

| metric | value |
|---|---:|
| total_runs | 1000 |
| ok_runs | 950 |
| failed_runs | 50 |
| skipped_llm_runs | 748 |
| total_llm_calls | 202 |
| tokens_in | 27674 |
| tokens_out | 11371 |
| latency_p50_ms | 0 |
| latency_p95_ms | 1869 |
| latency_p99_ms | 3112 |
| budget_breach_count | 0 |
| escalation_required_count | 0 |

- 74.8% of runs skipped LLM via deterministic-first + skip logic.
- LLM was invoked 202 times out of 1000 runs (20.2%).
- Failures (50) were captured at VERIFY stage as OUTPUT_SCHEMA_INVALID (expected exhaustion cohort).
- p95/p99 latency observed: 1869ms / 3112ms; mean 359ms.

stage_counts: {"ADAPTER": 950, "DETERMINISTIC": 950, "VERIFY": 50}
error_type_counts: {"OUTPUT_SCHEMA_INVALID": 50}
