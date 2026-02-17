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

app = FastAPI(title="KORA Studio Backend", version="0.1.0")
RUNS: dict[str, dict[str, Any]] = {}

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


def _build_graph(prompt: str, adapter: str) -> TaskGraph:
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
    graph = _build_graph(payload.prompt, adapter=adapter)
    result = run_graph(graph)
    run_id = uuid4().hex
    events = result.get("events", [])
    if not isinstance(events, list):
        events = []
    RUNS[run_id] = {"events": events, "done": True}
    return {"run_id": run_id}


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
            payload = json.dumps({"stage": stage, "status": status}, separators=(",", ":"))
            yield f"event: station\ndata: {payload}\n\n"
            await asyncio.sleep(0.3)

        if await request.is_disconnected():
            return
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
