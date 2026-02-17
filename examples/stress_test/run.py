"""Stress-test harness for mixed KORA workloads."""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kora.executor import run_graph
from kora.task_ir import TaskGraph, normalize_graph, validate_graph
from kora.telemetry import summarize_run

SHORT_TEXT = "Summarize quickly."
LONG_TEXT = (
    "Inference costs have become one of the largest line-items for modern AI applications. "
    "Teams often call an LLM at every step, causing cost and latency volatility. "
    "A structured runtime can execute deterministic tasks locally and call models only when needed."
)


def _percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    idx = max(0, min(len(values) - 1, int(round((len(values) - 1) * pct))))
    return sorted(values)[idx]


def _build_graph(
    *,
    idx: int,
    text: str,
    adapter: str,
    force_budget_failure: bool,
) -> TaskGraph:
    llm_budget = {"max_time_ms": 3000, "max_tokens": 400, "max_retries": 1}
    if force_budget_failure:
        llm_budget = {"max_time_ms": 1, "max_tokens": 1, "max_retries": 0}

    det_verify_schema: dict[str, Any] = {"type": "object", "required": ["status", "task_id", "is_simple"]}
    if force_budget_failure:
        # Intentionally fail verification in exhaustion scenarios while still applying extreme budgets.
        det_verify_schema = {
            "type": "object",
            "required": ["status", "task_id", "is_simple", "must_fail_on_exhaustion_case"],
        }

    graph_payload: dict[str, Any] = {
        "graph_id": f"stress-{idx}",
        "version": "0.1",
        "root": "task_llm",
        "defaults": {"budget": {"max_time_ms": 3000, "max_tokens": 400, "max_retries": 1}},
        "tasks": [
            {
                "id": "task_pre",
                "type": "det.classify_simple",
                "deps": [],
                "in": {"text": text},
                "run": {"kind": "det", "spec": {"handler": "classify_simple", "args": {"text": text}}},
                "verify": {
                    "schema": det_verify_schema,
                    "rules": [{"kind": "required", "paths": ["status", "task_id", "is_simple"]}],
                },
                "policy": {"on_fail": "fail"},
                "tags": ["stress"],
            },
            {
                "id": "task_llm",
                "type": "llm.answer",
                "deps": ["task_pre"],
                "in": {},
                "run": {
                    "kind": "llm",
                    "spec": {
                        "adapter": adapter,
                        "input": {"question": text, "skip_if": {"path": "$.is_simple", "equals": True}},
                        "output_schema": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string"},
                                "task_id": {"type": "string"},
                                "answer": {"type": "string"},
                            },
                            "required": ["status", "task_id", "answer"],
                        },
                    },
                },
                "verify": {
                    "schema": {"type": "object", "required": ["status", "task_id", "answer"]},
                    "rules": [],
                },
                "policy": {"budget": llm_budget, "on_fail": "retry"},
                "tags": ["stress"],
            },
        ],
    }
    graph = TaskGraph.model_validate(graph_payload)
    normalized = normalize_graph(graph)
    validate_graph(normalized)
    return normalized


def _render_markdown(report: dict[str, Any]) -> str:
    params = report["params"]
    s = report["summary"]
    return "\n".join(
        [
            f"# Stress Test Report ({report['timestamp']})",
            "",
            "## Parameters",
            "",
            f"- n: {params['n']}",
            f"- mix: {params['mix']}",
            f"- seed: {params['seed']}",
            f"- adapter: {params['adapter']}",
            f"- exhaustion_runs: {params['exhaustion_runs']}",
            "",
            "## Summary",
            "",
            "| metric | value |",
            "|---|---:|",
            f"| total_runs | {s['total_runs']} |",
            f"| ok_runs | {s['ok_runs']} |",
            f"| failed_runs | {s['failed_runs']} |",
            f"| skipped_llm_runs | {s['skipped_llm_runs']} |",
            f"| total_llm_calls | {s['total_llm_calls']} |",
            f"| tokens_in | {s['tokens_in']} |",
            f"| tokens_out | {s['tokens_out']} |",
            f"| latency_p50_ms | {s['latency_ms']['p50']} |",
            f"| latency_p95_ms | {s['latency_ms']['p95']} |",
            f"| latency_p99_ms | {s['latency_ms']['p99']} |",
            f"| budget_breach_count | {s['budget_breach_count']} |",
            f"| escalation_required_count | {s['escalation_required_count']} |",
            "",
            "## Breakdown",
            "",
            f"- stage_counts: {json.dumps(s['stage_counts'], sort_keys=True)}",
            f"- error_type_counts: {json.dumps(s['error_type_counts'], sort_keys=True)}",
        ]
    ) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run mixed workload stress tests.")
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--mix", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--use-openai", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out", default="docs/reports/stress_report")
    args = parser.parse_args()

    n = max(1, int(args.n))
    mix = min(max(float(args.mix), 0.0), 1.0)
    rng = random.Random(int(args.seed))

    use_openai = bool(args.use_openai) and bool(os.getenv("OPENAI_API_KEY"))
    adapter = "openai" if use_openai else "mock"
    exhaustion_runs = max(50, int(round(n * 0.05)))
    exhaustion_indices = set(rng.sample(range(n), min(exhaustion_runs, n)))

    total_llm_calls = 0
    skipped_llm_runs = 0
    ok_runs = 0
    failed_runs = 0
    tokens_in = 0
    tokens_out = 0
    budget_breach_count = 0
    escalation_required_count = 0
    stage_counts: dict[str, int] = {}
    error_type_counts: dict[str, int] = {}
    latencies_ms: list[int] = []

    start_all = time.monotonic()
    for idx in range(n):
        is_trivial = rng.random() < mix
        text = SHORT_TEXT if is_trivial else LONG_TEXT
        force_budget_failure = idx in exhaustion_indices

        graph_start = time.monotonic()
        graph = _build_graph(
            idx=idx,
            text=text,
            adapter=adapter,
            force_budget_failure=force_budget_failure,
        )
        result = run_graph(graph)
        total_time_ms = int((time.monotonic() - graph_start) * 1000)
        latencies_ms.append(total_time_ms)

        run_summary = summarize_run(result)
        if run_summary["ok"]:
            ok_runs += 1
        else:
            failed_runs += 1

        total_llm_calls += int(run_summary["total_llm_calls"])
        tokens_in += int(run_summary["tokens_in"])
        tokens_out += int(run_summary["tokens_out"])
        budget_breach_count += int(run_summary["budget_breaches"])
        escalation_required_count += int(run_summary["escalation_required"])

        for stage, count in run_summary["stage_counts"].items():
            stage_counts[stage] = stage_counts.get(stage, 0) + int(count)

        if run_summary["events_skipped"] > 0:
            skipped_llm_runs += 1

        err = result.get("error")
        if isinstance(err, dict):
            error_type = str(err.get("error_type", "UNKNOWN"))
            error_type_counts[error_type] = error_type_counts.get(error_type, 0) + 1

    summary = {
        "total_runs": n,
        "ok_runs": ok_runs,
        "failed_runs": failed_runs,
        "skipped_llm_runs": skipped_llm_runs,
        "total_llm_calls": total_llm_calls,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_ms": {
            "p50": _percentile(latencies_ms, 0.50),
            "p95": _percentile(latencies_ms, 0.95),
            "p99": _percentile(latencies_ms, 0.99),
            "mean": int(statistics.mean(latencies_ms)) if latencies_ms else 0,
        },
        "stage_counts": dict(sorted(stage_counts.items())),
        "error_type_counts": dict(sorted(error_type_counts.items())),
        "budget_breach_count": budget_breach_count,
        "escalation_required_count": escalation_required_count,
        "wall_time_ms": int((time.monotonic() - start_all) * 1000),
    }

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "params": {
            "n": n,
            "mix": mix,
            "seed": int(args.seed),
            "adapter": adapter,
            "use_openai_requested": bool(args.use_openai),
            "use_openai_effective": use_openai,
            "exhaustion_runs": min(exhaustion_runs, n),
        },
        "summary": summary,
    }

    out_base = Path(args.out)
    out_base.parent.mkdir(parents=True, exist_ok=True)
    json_path = out_base.with_suffix(".json")
    md_path = out_base.with_suffix(".md")
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")

    print(f"Stress run complete: n={n}, ok={ok_runs}, failed={failed_runs}, adapter={adapter}")
    print(f"Wrote JSON report: {json_path}")
    print(f"Wrote Markdown report: {md_path}")


if __name__ == "__main__":
    main()
