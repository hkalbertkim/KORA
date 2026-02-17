"""Production-like real workload harness for direct vs KORA execution."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kora.adapters.openai_adapter import OpenAIAdapter
from kora.executor import normalize_answer_json_string, run_graph
from kora.task_ir import TaskGraph, normalize_graph, validate_graph

DEFAULT_REQUEST = (
    "User asks for a concise summary of cost variance risks in an AI support assistant rollout."
)
REPORT_PATH = Path("docs/reports/real_app_benchmark.json")


def _build_graph(request_text: str) -> TaskGraph:
    payload = {
        "graph_id": "real-workload-harness",
        "version": "0.1",
        "root": "task_llm",
        "defaults": {"budget": {"max_time_ms": 3000, "max_tokens": 400, "max_retries": 1}},
        "tasks": [
            {
                "id": "task_pre",
                "type": "det.classify_simple",
                "deps": [],
                "in": {"text": request_text},
                "run": {
                    "kind": "det",
                    "spec": {
                        "handler": "classify_simple",
                        "args": {"text": request_text},
                    },
                },
                "verify": {
                    "schema": {"type": "object", "required": ["status", "task_id", "is_simple"]},
                    "rules": [{"kind": "required", "paths": ["status", "task_id", "is_simple"]}],
                },
                "policy": {"on_fail": "fail"},
                "tags": ["real-workload"],
            },
            {
                "id": "task_llm",
                "type": "llm.answer",
                "deps": ["task_pre"],
                "in": {},
                "run": {
                    "kind": "llm",
                    "spec": {
                        "adapter": "openai",
                        "input": {
                            "question": request_text,
                            "skip_if": {"path": "$.is_simple", "equals": True},
                        },
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
                "policy": {"budget": {"max_time_ms": 3000, "max_tokens": 400, "max_retries": 1}, "on_fail": "retry"},
                "tags": ["real-workload"],
            },
        ],
    }
    graph = TaskGraph.model_validate(payload)
    normalized = normalize_graph(graph)
    validate_graph(normalized)
    return normalized


def _summarize_kora_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    ok_count = sum(1 for event in events if event.get("status") == "ok")
    fail_count = sum(1 for event in events if event.get("status") == "fail")
    skipped_count = sum(1 for event in events if event.get("skipped") is True)
    stages: dict[str, int] = {}
    for event in events:
        stage = str(event.get("stage", "UNKNOWN"))
        stages[stage] = stages.get(stage, 0) + 1
    return {"ok": ok_count, "fail": fail_count, "skipped": skipped_count, "stages": stages}


def _run_direct(request_text: str) -> dict[str, Any]:
    adapter = OpenAIAdapter()
    output_schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "task_id": {"type": "string"},
            "answer": {"type": "string"},
        },
        "required": ["status", "task_id", "answer"],
    }
    start = time.monotonic()
    result = adapter.run(
        task_id="direct_call",
        input={"question": request_text},
        budget={"max_time_ms": 3000, "max_tokens": 400, "max_retries": 0},
        output_schema=output_schema,
    )
    usage = result.get("usage", {})
    return {
        "mode": "direct",
        "provider": "openai",
        "model": result.get("meta", {}).get("model", adapter.model),
        "total_llm_calls": 1 if result.get("ok") else 0,
        "tokens_in": int(usage.get("tokens_in", 0)),
        "tokens_out": int(usage.get("tokens_out", 0)),
        "total_time_ms": int((time.monotonic() - start) * 1000),
        "kora_events": {"ok": 0, "fail": 0, "skipped": 0, "stages": {}},
        "final": normalize_answer_json_string(result.get("output", {})),
        "ok": bool(result.get("ok")),
        "error": result.get("error"),
    }


def _run_kora(request_text: str) -> dict[str, Any]:
    graph = _build_graph(request_text)
    start = time.monotonic()
    result = run_graph(graph)
    events = result.get("events", [])
    llm_events = [
        event
        for event in events
        if event.get("task_id") == "task_llm"
        and event.get("status") == "ok"
        and not event.get("skipped", False)
    ]
    tokens_in = sum(int(event.get("usage", {}).get("tokens_in", 0)) for event in llm_events)
    tokens_out = sum(int(event.get("usage", {}).get("tokens_out", 0)) for event in llm_events)
    return {
        "mode": "kora",
        "provider": "openai",
        "model": OpenAIAdapter().model,
        "total_llm_calls": len(llm_events),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "total_time_ms": int((time.monotonic() - start) * 1000),
        "kora_events": _summarize_kora_events(events),
        "final": result.get("final"),
        "ok": bool(result.get("ok")),
        "error": result.get("error"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run production-like benchmark harness.")
    parser.add_argument("--mode", choices=["direct", "kora"], default="kora")
    parser.add_argument("--request", default=DEFAULT_REQUEST)
    args = parser.parse_args()

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).isoformat()

    if not os.getenv("OPENAI_API_KEY"):
        report = {
            "timestamp": timestamp,
            "mode": args.mode,
            "provider": "openai",
            "model": OpenAIAdapter().model,
            "total_llm_calls": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "total_time_ms": 0,
            "kora_events": {"ok": 0, "fail": 0, "skipped": 0, "stages": {}},
            "final": None,
            "ok": False,
            "error": "OPENAI_API_KEY is missing; skipped runtime benchmark call.",
        }
        REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("OPENAI_API_KEY is missing; skipped runtime benchmark call.")
        print(f"Wrote report: {REPORT_PATH}")
        return

    mode_result = _run_direct(args.request) if args.mode == "direct" else _run_kora(args.request)
    report = {
        "timestamp": timestamp,
        "mode": mode_result["mode"],
        "provider": mode_result["provider"],
        "model": mode_result["model"],
        "total_llm_calls": mode_result["total_llm_calls"],
        "tokens_in": mode_result["tokens_in"],
        "tokens_out": mode_result["tokens_out"],
        "total_time_ms": mode_result["total_time_ms"],
        "kora_events": mode_result["kora_events"],
        "final": mode_result["final"],
    }
    if mode_result.get("error"):
        report["error"] = mode_result["error"]

    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Wrote report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
