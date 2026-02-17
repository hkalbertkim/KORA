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
