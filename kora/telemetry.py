"""Telemetry helpers for KORA run outputs and harness reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input JSON must be an object")
    return payload


def summarize_run(obj: dict[str, Any]) -> dict[str, Any]:
    events = obj.get("events")
    if not isinstance(events, list):
        events = []

    kora_events = obj.get("kora_events")
    if not isinstance(kora_events, dict):
        kora_events = {}

    ok = bool(obj.get("ok", True))
    total_time_ms = int(obj.get("total_time_ms", 0))
    if total_time_ms == 0 and events:
        total_time_ms = sum(int(event.get("time_ms", 0)) for event in events if isinstance(event, dict))

    total_llm_calls = int(obj.get("total_llm_calls", 0))
    if total_llm_calls == 0 and events:
        total_llm_calls = sum(
            1
            for event in events
            if isinstance(event, dict)
            and event.get("stage") == "ADAPTER"
            and event.get("status") == "ok"
            and not event.get("skipped", False)
        )

    tokens_in = int(obj.get("tokens_in", 0))
    tokens_out = int(obj.get("tokens_out", 0))
    if (tokens_in == 0 and tokens_out == 0) and events:
        tokens_in = sum(
            int((event.get("usage") or {}).get("tokens_in", 0))
            for event in events
            if isinstance(event, dict)
        )
        tokens_out = sum(
            int((event.get("usage") or {}).get("tokens_out", 0))
            for event in events
            if isinstance(event, dict)
        )

    if events:
        events_ok = sum(1 for event in events if isinstance(event, dict) and event.get("status") == "ok")
        events_fail = sum(1 for event in events if isinstance(event, dict) and event.get("status") == "fail")
        events_skipped = sum(
            1 for event in events if isinstance(event, dict) and event.get("skipped") is True
        )
        stage_counts: dict[str, int] = {}
        for event in events:
            if not isinstance(event, dict):
                continue
            stage = event.get("stage")
            if stage is None:
                continue
            key = str(stage)
            stage_counts[key] = stage_counts.get(key, 0) + 1
    else:
        events_ok = int(kora_events.get("ok", 0))
        events_fail = int(kora_events.get("fail", 0))
        events_skipped = int(kora_events.get("skipped", 0))
        stage_counts = {
            str(k): int(v)
            for k, v in (kora_events.get("stages", {}) or {}).items()
        }

    budget_breaches = 0
    escalation_required = 0
    top_error = obj.get("error")
    if isinstance(top_error, dict):
        if bool(top_error.get("budget_breached")):
            budget_breaches += 1
        if top_error.get("error_type") == "ESCALATE_REQUIRED":
            escalation_required += 1

    for event in events:
        if not isinstance(event, dict):
            continue
        error = event.get("error")
        if not isinstance(error, dict):
            continue
        if bool(error.get("budget_breached")):
            budget_breaches += 1
        if error.get("error_type") == "ESCALATE_REQUIRED":
            escalation_required += 1

    return {
        "ok": ok,
        "total_time_ms": total_time_ms,
        "total_llm_calls": total_llm_calls,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "events_ok": events_ok,
        "events_fail": events_fail,
        "events_skipped": events_skipped,
        "stage_counts": stage_counts,
        "budget_breaches": budget_breaches,
        "escalation_required": escalation_required,
    }
