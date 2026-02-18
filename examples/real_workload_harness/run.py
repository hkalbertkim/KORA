"""Production-like real workload harness for direct vs KORA execution."""

from __future__ import annotations

import argparse
import json
import os
import re
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
OUTPUT_CONTRACT = "OUTPUT:JSON slides[{i,title,msg,bullets[],notes}]"


def _parse_constraints_for_prompt(request_text: str) -> dict[str, Any]:
    lowered = request_text.lower()
    slide_match = re.search(r"(\d+)\s*-\s*slide|(\d+)\s+slides?", lowered)
    slide_count = 18
    if slide_match:
        number = next((g for g in slide_match.groups() if g), None)
        if number and number.isdigit():
            slide_count = int(number)

    topic_domains: list[str] = []
    phrase_map = [
        ("market context", "market_context"),
        ("architecture", "architecture"),
        ("decomposition", "decomposition"),
        ("escalation", "escalation"),
        ("benchmark", "benchmarking"),
        ("rollout", "rollout_plan"),
        ("risk", "risk"),
        ("recommendation", "recommendations"),
    ]
    for phrase, label in phrase_map:
        if phrase in lowered:
            topic_domains.append(label)
    if not topic_domains:
        topic_domains = ["strategy", "execution"]

    return {
        "intent": "create_presentation_outline",
        "deliverable_type": "ppt_outline",
        "slide_count": slide_count,
        "required_components": ["title", "key_message", "bullets", "presenter_notes"],
        "topic_domains": topic_domains[:8],
    }


def _build_compact_llm_question(request_text: str) -> str:
    parsed = _parse_constraints_for_prompt(request_text)
    slide_count = int(parsed.get("slide_count", 18))
    domain_tags = [str(tag).strip().lower().replace("_", "") for tag in parsed.get("topic_domains", [])][:8]
    include_line = "|".join(domain_tags) if domain_tags else "market|arch|decomposition|escalation|bench|rollout|risks|recs"
    return (
        "TASK:PPT_OUTLINE\n"
        f"SLIDES:{slide_count}\n"
        "FIELDS:title|key_message|bullets(3-5)|notes\n"
        f"INCLUDE:{include_line}\n"
        f"{OUTPUT_CONTRACT}"
    )


def _build_raw_llm_question(request_text: str) -> str:
    return (
        "TASK:PPT_OUTLINE\n"
        f"REQUEST:{request_text}\n"
        "FIELDS:title|key_message|bullets(3-5)|notes\n"
        f"{OUTPUT_CONTRACT}"
    )


def _build_graph(request_text: str) -> TaskGraph:
    baseline_raw = os.getenv("KORA_BASELINE_RAW", "") == "1"
    hier_escalation = os.getenv("KORA_HIER_ESCALATION", "") == "1"
    compact_question = _build_raw_llm_question(request_text) if baseline_raw else _build_compact_llm_question(request_text)
    root_task = "task_llm_full" if hier_escalation else "task_llm"

    tasks: list[dict[str, Any]] = [
        {
            "id": "task_parse_constraints",
            "type": "det.parse_request_constraints",
            "deps": [],
            "in": {"text": request_text},
            "run": {
                "kind": "det",
                "spec": {
                    "handler": "parse_request_constraints",
                    "args": {"text": request_text},
                },
            },
            "verify": {
                "schema": {
                    "type": "object",
                    "required": [
                        "status",
                        "task_id",
                        "intent",
                        "deliverable_type",
                        "slide_count",
                        "required_components",
                        "topic_domains",
                    ],
                },
                "rules": [],
            },
            "policy": {"on_fail": "fail"},
            "tags": ["real-workload", "constraint-parse"],
        },
        {
            "id": "task_pre",
            "type": "det.classify_simple",
            "deps": ["task_parse_constraints"],
            "in": {"text": compact_question},
            "run": {
                "kind": "det",
                "spec": {
                    "handler": "classify_simple",
                    "args": {"text": compact_question},
                },
            },
            "verify": {
                "schema": {"type": "object", "required": ["status", "task_id", "is_simple"]},
                "rules": [{"kind": "required", "paths": ["status", "task_id", "is_simple"]}],
            },
            "policy": {"on_fail": "fail"},
            "tags": ["real-workload"],
        },
    ]

    if hier_escalation:
        mini_question = (
            "TASK:MINI_SKELETON\n"
            f"REQ:{compact_question}\n"
            "Return ONLY valid JSON. No prose. No markdown. No code fences.\n"
            "Top-level JSON keys MUST be exactly: status, task_id, slides.\n"
            "Set status='ok' and task_id='task_llm_mini'.\n"
            "slides must be an array of exactly 18 objects.\n"
            "Each slide object MUST include keys: i,title,msg,bullets.\n"
            "bullets MUST be an array with 0 or 1 short strings.\n"
        )
        full_question = (
            "TASK:FULL_REFINE\n"
            "INPUT:mini skeleton from prior step\n"
            f"CONSTRAINTS:{compact_question}\n"
            f"{OUTPUT_CONTRACT}"
        )
        tasks.extend(
            [
                {
                    "id": "task_llm_mini",
                    "type": "llm.answer.mini",
                    "deps": ["task_pre"],
                    "in": {},
                    "run": {
                        "kind": "llm",
                        "spec": {
                            "adapter": "openai_mini",
                            "input": {
                                "question": mini_question,
                                "skip_if": {"path": "$.is_simple", "equals": True},
                            },
                            "output_schema": {
                                "type": "object",
                                "properties": {
                                    "status": {"type": "string"},
                                    "task_id": {"type": "string"},
                                    "slides": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "i": {"type": "integer"},
                                                "title": {"type": "string"},
                                                "msg": {"type": "string"},
                                                "bullets": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                    "minItems": 0,
                                                    "maxItems": 1,
                                                },
                                            },
                                            "required": ["i", "title", "msg", "bullets"],
                                        },
                                    },
                                },
                                "required": ["status", "task_id", "slides"],
                            },
                        },
                    },
                    "verify": {
                        "schema": {"type": "object", "required": ["status", "task_id", "slides"]},
                        "rules": [],
                    },
                    "policy": {
                        "budget": {"max_time_ms": 12000, "max_tokens": 220, "max_retries": 1},
                        "on_fail": "retry",
                    },
                    "tags": ["real-workload", "hier-mini"],
                },
                {
                    "id": "task_quality_gate",
                    "type": "det.quality_gate",
                    "deps": ["task_llm_mini"],
                    "in": {},
                    "run": {
                        "kind": "det",
                        "spec": {
                            "handler": "quality_gate",
                            "args": {
                                "dep_task_id": "task_llm_mini",
                                "target_slide_count": 18,
                                "required_fields": ["i", "title", "msg", "bullets"],
                            },
                        },
                    },
                    "verify": {
                        "schema": {
                            "type": "object",
                            "required": ["status", "task_id", "message", "needs_refine", "reason"],
                        },
                        "rules": [],
                    },
                    "policy": {"on_fail": "fail"},
                    "tags": ["real-workload", "hier-gate"],
                },
                {
                    "id": "task_llm_full",
                    "type": "llm.answer.full",
                    "deps": ["task_quality_gate"],
                    "in": {},
                    "run": {
                        "kind": "llm",
                        "spec": {
                            "adapter": "openai_full",
                            "input": {
                                "question": full_question,
                                "skip_if": {"path": "$.message", "equals": "skip_full"},
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
                    "policy": {
                        "budget": {"max_time_ms": 22000, "max_tokens": 400, "max_retries": 1},
                        "on_fail": "retry",
                    },
                    "tags": ["real-workload", "hier-full"],
                },
            ]
        )
    else:
        tasks.append(
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
                            "question": compact_question,
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
                "policy": {
                    "budget": {"max_time_ms": 20000, "max_tokens": 400, "max_retries": 1},
                    "on_fail": "retry",
                },
                "tags": ["real-workload"],
            }
        )

    payload = {
        "graph_id": "real-workload-harness",
        "version": "0.1",
        "root": root_task,
        "defaults": {"budget": {"max_time_ms": 20000, "max_tokens": 400, "max_retries": 1}},
        "tasks": tasks,
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
        if "stage" not in event:
            continue
        stage = str(event["stage"])
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
    start = time.monotonic()
    graph = _build_graph(request_text)
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
