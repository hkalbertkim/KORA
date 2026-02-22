from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from kora.executor import run_graph
from kora.task_ir import TaskGraph, normalize_graph, validate_graph
from kora.telemetry import summarize_run

app = FastAPI(title="KORA Studio Backend", version="0.1.0")
RUNS: dict[str, dict[str, Any]] = {}
EVENT_META_WHITELIST = (
    "stop_reason",
    "gate_retrieval_hit",
    "gate_retrieval_strategy",
    "gate_verifier_ok",
    "adapter",
    "model",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _repo_root() -> Path:
    return REPO_ROOT


def _load_demo_report() -> dict[str, Any]:
    report_path = _repo_root() / "docs" / "reports" / "real_app_benchmark.telemetry.json"
    if report_path.exists():
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload

    return {
        "ok": True,
        "total_time_ms": 4842,
        "total_llm_calls": 1,
        "tokens_in": 188,
        "tokens_out": 187,
        "estimated_cost_usd": 0.0001404,
        "events_ok": 2,
        "events_fail": 0,
        "events_skipped": 0,
        "stage_counts": {"DETERMINISTIC": 1, "ADAPTER": 1},
        "budget_breaches": 0,
        "escalation_required": 0,
    }


class RunRequest(BaseModel):
    prompt: str
    mode: str = "kora"
    adapter: str = "mock"


def _build_graph(prompt: str, adapter: str, mode: str) -> TaskGraph:
    if mode == "direct":
        payload = {
            "graph_id": f"studio-{uuid4().hex[:8]}",
            "version": "0.1",
            "root": "task_llm",
            "defaults": {"budget": {"max_time_ms": 3000, "max_tokens": 400, "max_retries": 1}},
            "tasks": [
                {
                    "id": "task_llm",
                    "type": "llm.answer",
                    "deps": [],
                    "in": {},
                    "run": {
                        "kind": "llm",
                        "spec": {
                            "adapter": adapter,
                            "input": {"question": prompt},
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
                        "budget": {"max_time_ms": 3000, "max_tokens": 400, "max_retries": 1},
                        "on_fail": "retry",
                    },
                    "tags": ["studio", "direct"],
                }
            ],
        }
        graph = TaskGraph.model_validate(payload)
        normalized = normalize_graph(graph)
        validate_graph(normalized)
        return normalized

    payload = {
        "graph_id": f"studio-{uuid4().hex[:8]}",
        "version": "0.1",
        "root": "task_llm",
        "defaults": {"budget": {"max_time_ms": 3000, "max_tokens": 400, "max_retries": 1}},
        "tasks": [
            {
                "id": "task_pre",
                "type": "det.classify_simple",
                "deps": [],
                "in": {"text": prompt},
                "run": {"kind": "det", "spec": {"handler": "classify_simple", "args": {"text": prompt}}},
                "verify": {
                    "schema": {"type": "object", "required": ["status", "task_id", "is_simple"]},
                    "rules": [{"kind": "required", "paths": ["status", "task_id", "is_simple"]}],
                },
                "policy": {"on_fail": "fail"},
                "tags": ["studio"],
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
                        "input": {"question": prompt, "skip_if": {"path": "$.is_simple", "equals": True}},
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
                "tags": ["studio"],
            },
        ],
    }
    graph = TaskGraph.model_validate(payload)
    normalized = normalize_graph(graph)
    validate_graph(normalized)
    return normalized


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/demo_report")
def demo_report() -> dict[str, Any]:
    return _load_demo_report()


@app.get("/api/demo_trace")
def demo_trace() -> list[dict[str, Any]]:
    return [
        {"station": "Input", "t": 0},
        {"station": "Deterministic", "t": 1},
        {"station": "Decision", "t": 2, "route": "adapter"},
        {"station": "Adapter", "t": 3},
        {"station": "Verify", "t": 4},
        {"station": "Output", "t": 5},
    ]


@app.post("/api/run")
def run_demo(payload: RunRequest) -> dict[str, str]:
    adapter = payload.adapter if payload.adapter in {"openai", "mock"} else "mock"
    mode = payload.mode if payload.mode in {"kora", "direct"} else "kora"
    graph = _build_graph(payload.prompt, adapter=adapter, mode=mode)
    result = run_graph(graph)
    run_id = uuid4().hex
    raw_events = result.get("events", [])
    events: list[dict[str, Any]] = []
    if isinstance(raw_events, list):
        for event in raw_events:
            if not isinstance(event, dict):
                continue
            normalized: dict[str, Any] = {
                "stage": event.get("stage"),
                "status": event.get("status"),
                "time_ms": event.get("time_ms"),
            }
            skipped = None
            if "skipped" in event:
                skipped = bool(event.get("skipped"))
            elif (
                str(event.get("stage", "")).upper() == "ADAPTER"
                and str(event.get("status", "")).lower() == "ok"
                and isinstance(event.get("message"), str)
                and "skip" in str(event.get("message", "")).lower()
            ):
                skipped = True
            if skipped is not None:
                normalized["skipped"] = skipped
            usage = event.get("usage")
            if isinstance(usage, dict):
                normalized["usage"] = usage
            error = event.get("error")
            if isinstance(error, dict):
                normalized["error"] = error
            meta_in = event.get("meta")
            if isinstance(meta_in, dict):
                meta_out = {k: meta_in.get(k) for k in EVENT_META_WHITELIST if k in meta_in}
                normalized["meta"] = meta_out
            events.append(normalized)
    summary = summarize_run(result)
    RUNS[run_id] = {
        "events": events,
        "summary": summary,
        "prompt": payload.prompt,
        "mode": mode,
        "ok": bool(result.get("ok", True)),
        "done": True,
    }
    return {"run_id": run_id}


@app.get("/api/run_history")
def run_history() -> list[dict[str, Any]]:
    items = list(RUNS.items())[-5:]
    return [
        {
            "run_id": run_id,
            "prompt": run.get("prompt", ""),
            "mode": run.get("mode", "kora"),
            "summary": run.get("summary", {}),
        }
        for run_id, run in reversed(items)
    ]


@app.get("/api/sse_run")
async def sse_run(request: Request, run_id: str | None = None) -> StreamingResponse:
    run = RUNS.get(run_id or "")

    async def _error_stream() -> AsyncGenerator[str, None]:
        yield 'event: done\ndata: {"ok":false,"error":"run_id not found"}\n\n'

    async def _run_stream() -> AsyncGenerator[str, None]:
        assert isinstance(run, dict)
        events = run.get("events", [])
        if not isinstance(events, list):
            events = []

        for event in events:
            if await request.is_disconnected():
                return
            if not isinstance(event, dict):
                continue
            stage = str(event.get("stage", "UNKNOWN"))
            status = str(event.get("status", "ok"))
            payload_obj: dict[str, Any] = {
                "stage": stage,
                "status": status,
                "time_ms": int(event.get("time_ms", 0)),
            }
            if "skipped" in event:
                payload_obj["skipped"] = bool(event.get("skipped"))
            usage = event.get("usage")
            if isinstance(usage, dict):
                if "tokens_in" in usage:
                    payload_obj["tokens_in"] = int(usage.get("tokens_in", 0))
                if "tokens_out" in usage:
                    payload_obj["tokens_out"] = int(usage.get("tokens_out", 0))
            meta = event.get("meta")
            if isinstance(meta, dict):
                payload_obj["meta"] = meta
            else:
                payload_obj["meta"] = {}
            payload = json.dumps(payload_obj, separators=(",", ":"))
            yield f"event: station\ndata: {payload}\n\n"
            await asyncio.sleep(0.3)

        if await request.is_disconnected():
            return
        summary = run.get("summary", {})
        if isinstance(summary, dict):
            summary_payload: dict[str, Any] = {
                "ok": bool(summary.get("ok", run.get("ok", True))),
                "total_time_ms": int(summary.get("total_time_ms", 0)),
                "total_llm_calls": int(summary.get("total_llm_calls", 0)),
                "tokens_in": int(summary.get("tokens_in", 0)),
                "tokens_out": int(summary.get("tokens_out", 0)),
            }
            if "estimated_cost_usd" in summary:
                summary_payload["estimated_cost_usd"] = float(summary["estimated_cost_usd"])
            yield f"event: summary\ndata: {json.dumps(summary_payload, separators=(',', ':'))}\n\n"
        yield 'event: done\ndata: {"ok":true}\n\n'

    if run is None:
        return StreamingResponse(_error_stream(), media_type="text/event-stream")
    return StreamingResponse(_run_stream(), media_type="text/event-stream")


@app.get("/api/sse_trace")
async def sse_trace(request: Request) -> StreamingResponse:
    trace = demo_trace()

    async def event_stream():
        for event in trace:
            if await request.is_disconnected():
                return
            payload = json.dumps(event, separators=(",", ":"))
            yield f"event: station\ndata: {payload}\n\n"
            await asyncio.sleep(0.4)

        if await request.is_disconnected():
            return
        yield 'event: done\ndata: {"ok":true}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")
