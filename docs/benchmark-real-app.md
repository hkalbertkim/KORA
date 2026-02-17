# Real Workload Benchmark Harness

## What This Simulates

`examples/real_workload_harness/run.py` simulates a production-like request path where:

- A direct baseline sends the request straight to `OpenAIAdapter`.
- A KORA path runs a TaskGraph with deterministic pre-classification (`classify_simple`) and an LLM task guarded by `skip_if`.

This gives a repeatable comparison of raw LLM execution vs structured runtime routing.

## How To Run

Direct baseline:

```bash
python3 examples/real_workload_harness/run.py --mode direct --request "Summarize customer escalation risk."
```

KORA mode:

```bash
python3 examples/real_workload_harness/run.py --mode kora --request "Summarize customer escalation risk."
```

Report output path:

`docs/reports/real_app_benchmark.json`

If `OPENAI_API_KEY` is missing, the harness skips the runtime call and writes a clear report with zeroed metrics.

### Telemetry Summary Export

Generate a deterministic telemetry summary from a saved report:

```bash
python3 -m kora.cli telemetry --input docs/reports/real_app_benchmark.json
```

or:

```bash
python3 -m kora telemetry --input docs/reports/real_app_benchmark.json
```

By default, JSON output is written next to the input file as:
`docs/reports/real_app_benchmark.telemetry.json`

## Captured Metrics

- `total_llm_calls`
- `tokens_in`
- `tokens_out`
- `total_time_ms`
- `kora_events` summary:
  - `ok`, `fail`, `skipped`
  - per-stage counts (`stages`)
- `final` output payload

Skip rate can be derived from `kora_events.skipped` against total KORA events.

## Results Placeholder

Example snippet:

```json
{
  "timestamp": "2026-02-17T10:00:00+00:00",
  "mode": "kora",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "total_llm_calls": 0,
  "tokens_in": 0,
  "tokens_out": 0,
  "total_time_ms": 12,
  "kora_events": {
    "ok": 2,
    "fail": 0,
    "skipped": 1,
    "stages": {
      "DETERMINISTIC": 1,
      "ADAPTER": 1
    }
  },
  "final": {
    "status": "ok",
    "task_id": "task_llm",
    "skipped": true,
    "message": "Skipped due to skip_if condition"
  }
}
```

## Measured Results (2026-02-17)

| Request | Mode | total_llm_calls | tokens_in | tokens_out | total_time_ms |
|---|---|---:|---:|---:|---:|
| Long request | Direct | 1 | 187 | 205 | 5154 |
| Long request | KORA | 1 | 188 | 187 | 4842 |

- Long calls equal (1call), KORA reduces tokens_out by 18 and is 312ms faster in this run.
- KORA provides structured events (stages) for observability; direct does not.
