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
        "final_output": result["final_output"],
        "events": result["events"],
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


def run_cases(offline: bool = False) -> dict[str, Any]:
    cases = {
        "short": _build_case(SHORT_TEXT, offline=offline),
        "long": _build_case(LONG_TEXT, offline=offline),
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


if __name__ == "__main__":
    main()
