"""Compare direct OpenAI call vs KORA flow with skip logic."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from kora.adapters.openai_adapter import OpenAIAdapter, harden_schema_for_openai
from kora.executor import run_graph
from kora.task_ir import TaskGraph, normalize_graph, validate_graph


def _load_direct_vs_kora_graph_data() -> dict[str, Any]:
    graph_path = Path(__file__).with_name("graph.json")
    return json.loads(graph_path.read_text(encoding="utf-8"))


def run_direct(query: str, llm_output_schema: dict[str, Any]) -> dict[str, Any]:
    hardened_schema = harden_schema_for_openai(llm_output_schema)

    if not os.getenv("OPENAI_API_KEY"):
        return {
            "ok": False,
            "llm_calls": 0,
            "error": "OPENAI_API_KEY missing; direct mode cannot call OpenAI",
            "usage": {"tokens_in": 0, "tokens_out": 0, "time_ms": 0},
            "output": {},
        }

    adapter = OpenAIAdapter()
    result = adapter.run(
        task_id="direct_call",
        input={"question": query},
        budget={"max_time_ms": 3000, "max_tokens": 400},
        output_schema=hardened_schema,
    )

    return {
        "ok": bool(result.get("ok")),
        "llm_calls": 1,
        "error": result.get("error"),
        "usage": result.get("usage", {"tokens_in": 0, "tokens_out": 0, "time_ms": 0}),
        "output": result.get("output", {}),
    }


def run_kora(query: str) -> dict[str, Any]:
    graph_data = _load_direct_vs_kora_graph_data()

    graph_data["tasks"][0]["in"]["text"] = query
    graph_data["tasks"][0]["run"]["spec"]["args"]["text"] = query
    graph_data["tasks"][1]["run"]["spec"]["input"]["question"] = query

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


def main() -> None:
    query = "Summarize this short question."
    graph_data = _load_direct_vs_kora_graph_data()
    llm_schema = graph_data["tasks"][1]["run"]["spec"]["output_schema"]

    direct_result = run_direct(query, llm_schema)
    kora_result = run_kora(query)

    summary = {
        "direct": direct_result,
        "kora": {
            "llm_calls": kora_result["llm_calls"],
            "tokens_in": kora_result["tokens_in"],
            "tokens_out": kora_result["tokens_out"],
            "final_output": kora_result["final_output"],
        },
        "comparison": {
            "llm_calls_reduced": direct_result["llm_calls"] - kora_result["llm_calls"],
        },
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
