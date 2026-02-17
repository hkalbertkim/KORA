from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="KORA Studio Backend", version="0.1.0")

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
    return Path(__file__).resolve().parents[3]


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
