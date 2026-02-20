"""Two-case direct-vs-kora benchmark for short and long inputs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from kora.adapters.mock import MockAdapter
from kora.adapters.openai_adapter import OpenAIAdapter, harden_schema_for_openai
from kora.executor import normalize_answer_json_string, run_graph
from kora.task_ir import TaskGraph, normalize_graph, validate_graph

SHORT_TEXT = "Summarize this short question."
LONG_TEXT = (
    "Enterprise teams deploying AI assistants in customer support often discover that raw model calls "
    "drive highly variable costs and latency because each request triggers full-context reasoning even for "
    "trivial intents. A practical orchestration layer can pre-classify request complexity, route simple "
    "questions through deterministic logic, and reserve model inference for ambiguous or high-value cases. "
    "This architecture improves margins, stabilizes response times, and creates clearer governance because "
    "every decision path is auditable, budgeted, and verifiable before responses reach end users."
)


def _load_graph_data() -> dict[str, Any]:
    graph_path = Path(__file__).with_name("graph.json")
    return json.loads(graph_path.read_text(encoding="utf-8"))


def _sum_tokens(usage: dict[str, Any] | None) -> tuple[int, int]:
    usage = usage or {}
    return int(usage.get("tokens_in", 0)), int(usage.get("tokens_out", 0))


def _run_direct_case(case_text: str, graph_data: dict[str, Any], offline: bool) -> dict[str, Any]:
    llm_task = graph_data["tasks"][1]
    llm_schema = llm_task["run"]["spec"]["output_schema"]
    llm_budget = llm_task["policy"]["budget"]
    hardened_schema = harden_schema_for_openai(llm_schema)

    adapter = MockAdapter() if offline else OpenAIAdapter()

    if not offline and not os.getenv("OPENAI_API_KEY"):
        return {
            "ok": False,
            "llm_calls": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "error": "OPENAI_API_KEY missing; direct mode cannot call OpenAI",
            "output": {},
            "model": OpenAIAdapter().model,
        }

    result = adapter.run(
        task_id="direct_call",
        input={"question": case_text},
        budget=llm_budget,
        output_schema=hardened_schema,
    )
    tokens_in, tokens_out = _sum_tokens(result.get("usage"))

    return {
        "ok": bool(result.get("ok")),
        "llm_calls": 1,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "error": result.get("error"),
        "output": normalize_answer_json_string(result.get("output", {})),
        "model": result.get("meta", {}).get("model", OpenAIAdapter().model),
    }


def _run_kora_case(case_text: str, offline: bool) -> dict[str, Any]:
    graph_data = _load_graph_data()
    graph_data["tasks"][0]["in"]["text"] = case_text
    graph_data["tasks"][0]["run"]["spec"]["args"]["text"] = case_text
    graph_data["tasks"][1]["run"]["spec"]["input"]["question"] = case_text

    if offline:
        graph_data["tasks"][1]["run"]["spec"]["adapter"] = "mock"

    graph = TaskGraph.model_validate(graph_data)
    normalized = normalize_graph(graph)
    validate_graph(normalized)
    result = run_graph(normalized)

    llm_events = [
        event
        for event in result["events"]
        if event["task_id"] == "task_llm" and not event.get("skipped", False)
    ]
    tokens_in = sum(int(event.get("usage", {}).get("tokens_in", 0)) for event in llm_events)
    tokens_out = sum(int(event.get("usage", {}).get("tokens_out", 0)) for event in llm_events)

    return {
        "llm_calls": len(llm_events),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "final_output": result["final"],
        "events": result["events"],
        "stage_timings": result.get("stage_timings", {}),
    }


def _build_case(case_text: str, offline: bool) -> dict[str, Any]:
    graph_data = _load_graph_data()
    direct = _run_direct_case(case_text, graph_data, offline=offline)
    kora = _run_kora_case(case_text, offline=offline)

    return {
        "direct": direct,
        "kora": kora,
        "comparison": {
            "llm_calls_reduced": direct["llm_calls"] - kora["llm_calls"],
            "tokens_in_reduced": direct["tokens_in"] - kora["tokens_in"],
            "tokens_out_reduced": direct["tokens_out"] - kora["tokens_out"],
        },
    }


def _run_det_no_schema_case() -> dict[str, Any]:
    graph = TaskGraph.model_validate(
        {
            "graph_id": "det-no-schema-short",
            "version": "0.1",
            "root": "task_echo",
            "defaults": {"budget": {"max_time_ms": 1500, "max_tokens": 300, "max_retries": 1}},
            "tasks": [
                {
                    "id": "task_echo",
                    "type": "det.echo",
                    "deps": [],
                    "in": {"message": "det_no_schema_short"},
                    "run": {"kind": "det", "spec": {"handler": "echo", "args": {}}},
                    "policy": {"on_fail": "fail"},
                    "tags": [],
                }
            ],
        }
    )
    normalized = normalize_graph(graph)
    validate_graph(normalized)
    result = run_graph(normalized)
    return {
        "direct": {"ok": True, "llm_calls": 0, "tokens_in": 0, "tokens_out": 0, "error": None, "output": {}, "model": "n/a"},
        "kora": {
            "llm_calls": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "final_output": result["final"],
            "events": result["events"],
            "stage_timings": result.get("stage_timings", {}),
        },
        "comparison": {"llm_calls_reduced": 0, "tokens_in_reduced": 0, "tokens_out_reduced": 0},
    }


def _stage_timing_breakdown(stage_timings: dict[str, Any] | None) -> dict[str, float] | None:
    if not isinstance(stage_timings, dict):
        return None
    overall_total_s = float(stage_timings.get("overall_total_s", 0.0) or 0.0)
    scheduler_total_s = float(stage_timings.get("scheduler_total_s", 0.0) or 0.0)
    det_total_s = float(stage_timings.get("det_total_s", 0.0) or 0.0)
    llm_total_s = float(stage_timings.get("llm_total_s", 0.0) or 0.0)
    verify_total_s = float(stage_timings.get("verify_total_s", 0.0) or 0.0)
    accounted_s = scheduler_total_s + det_total_s + llm_total_s + verify_total_s
    overhead_s = overall_total_s - accounted_s
    overhead_pct = (overhead_s / overall_total_s) if overall_total_s > 0.0 else 0.0
    return {
        "overall_total_s": overall_total_s,
        "scheduler_total_s": scheduler_total_s,
        "det_total_s": det_total_s,
        "llm_total_s": llm_total_s,
        "verify_total_s": verify_total_s,
        "overhead_s": overhead_s,
        "overhead_pct": overhead_pct,
    }


def _print_adaptive_routing_trace(case_name: str, events: list[dict[str, Any]] | None) -> None:
    if not isinstance(events, list):
        return
    llm_events = [
        event
        for event in events
        if event.get("task_id") == "task_llm" and not event.get("skipped", False)
    ]
    print(f"Adaptive Routing Trace ({case_name})")
    if not llm_events:
        print("- (none)")
        return
    for event in llm_events:
        meta = event.get("meta", {})
        if not isinstance(meta, dict):
            meta = {}
        step = event.get("escalation_step")
        confidence = meta.get("confidence")
        uncertainty = meta.get("uncertainty")
        estimated_next_cost = meta.get("estimated_next_cost")
        voi = meta.get("voi")
        stop_reason = meta.get("stop_reason")
        cost_units = meta.get("cost_units")
        print(
            "- step={step} conf={confidence} unc={uncertainty} est_cost={estimated_next_cost} "
            "voi={voi} stop={stop_reason} cost_units={cost_units}".format(
                step=step,
                confidence=confidence,
                uncertainty=uncertainty,
                estimated_next_cost=estimated_next_cost,
                voi=voi,
                stop_reason=stop_reason,
                cost_units=cost_units,
            )
        )


def run_cases(offline: bool = False) -> dict[str, Any]:
    cases = {
        "short": _build_case(SHORT_TEXT, offline=offline),
        "long": _build_case(LONG_TEXT, offline=offline),
        "det_no_schema_short": _run_det_no_schema_case(),
    }

    llm_calls_direct_total = sum(cases[name]["direct"]["llm_calls"] for name in ("short", "long"))
    llm_calls_kora_total = sum(cases[name]["kora"]["llm_calls"] for name in ("short", "long"))
    tokens_in_direct_total = sum(cases[name]["direct"]["tokens_in"] for name in ("short", "long"))
    tokens_in_kora_total = sum(cases[name]["kora"]["tokens_in"] for name in ("short", "long"))
    tokens_out_direct_total = sum(cases[name]["direct"]["tokens_out"] for name in ("short", "long"))
    tokens_out_kora_total = sum(cases[name]["kora"]["tokens_out"] for name in ("short", "long"))

    return {
        "cases": cases,
        "summary": {
            "llm_calls_direct_total": llm_calls_direct_total,
            "llm_calls_kora_total": llm_calls_kora_total,
            "llm_calls_reduced_total": llm_calls_direct_total - llm_calls_kora_total,
            "tokens_in_direct_total": tokens_in_direct_total,
            "tokens_in_kora_total": tokens_in_kora_total,
            "tokens_out_direct_total": tokens_out_direct_total,
            "tokens_out_kora_total": tokens_out_kora_total,
        },
    }


def main() -> None:
    offline = not bool(os.getenv("OPENAI_API_KEY"))
    payload = run_cases(offline=offline)
    print(json.dumps(payload, indent=2))
    for case_name in payload["cases"]:
        stage_timings = payload["cases"][case_name]["kora"].get("stage_timings")
        breakdown = _stage_timing_breakdown(stage_timings)
        if breakdown is None:
            continue
        print(f"\nStage Timing Breakdown ({case_name})")
        print(f"- overall_total_s: {breakdown['overall_total_s']:.6f}")
        print(f"- scheduler_total_s: {breakdown['scheduler_total_s']:.6f}")
        print(f"- det_total_s: {breakdown['det_total_s']:.6f}")
        print(f"- llm_total_s: {breakdown['llm_total_s']:.6f}")
        print(f"- verify_total_s: {breakdown['verify_total_s']:.6f}")
        print(f"- overhead_s: {breakdown['overhead_s']:.6f}")
        print(f"- overhead_pct: {breakdown['overhead_pct']:.6f}")
        print()
        _print_adaptive_routing_trace(case_name, payload["cases"][case_name]["kora"].get("events"))


if __name__ == "__main__":
    main()
