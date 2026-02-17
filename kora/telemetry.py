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

    summary = {
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
    timestamp = obj.get("timestamp")
    if isinstance(timestamp, str):
        summary["timestamp"] = timestamp
    error = obj.get("error")
    if isinstance(error, dict):
        summary["error"] = error
    return summary


def render_markdown_report(summary: dict[str, Any], *, source_path: str) -> str:
    timestamp = summary.get("timestamp")
    title = f"Telemetry Report ({timestamp})" if isinstance(timestamp, str) and timestamp else "Telemetry Report"

    stage_rows = []
    stage_counts = summary.get("stage_counts", {})
    if isinstance(stage_counts, dict) and stage_counts:
        for stage, count in sorted(stage_counts.items()):
            stage_rows.append(f"| {stage} | {int(count)} |")
    else:
        stage_rows.append("| (none) | 0 |")

    lines = [
        f"# {title}",
        "",
        f"Input file: `{source_path}`",
        "",
        "## Summary",
        "",
        "| ok | total_time_ms | total_llm_calls | tokens_in | tokens_out |",
        "|---|---:|---:|---:|---:|",
        (
            f"| {bool(summary.get('ok', False))} | {int(summary.get('total_time_ms', 0))} | "
            f"{int(summary.get('total_llm_calls', 0))} | {int(summary.get('tokens_in', 0))} | "
            f"{int(summary.get('tokens_out', 0))} |"
        ),
        "",
        "## Events",
        "",
        f"- events_ok: {int(summary.get('events_ok', 0))}",
        f"- events_fail: {int(summary.get('events_fail', 0))}",
        f"- events_skipped: {int(summary.get('events_skipped', 0))}",
        "",
        "## Stage Counts",
        "",
        "| stage | count |",
        "|---|---:|",
        *stage_rows,
        "",
        "## Policy Signals",
        "",
        f"- budget_breaches: {int(summary.get('budget_breaches', 0))}",
        f"- escalation_required: {int(summary.get('escalation_required', 0))}",
    ]

    if not bool(summary.get("ok", True)):
        error = summary.get("error")
        if isinstance(error, dict):
            lines.extend(
                [
                    "",
                    "## Failure",
                    "",
                    f"- error_type: {error.get('error_type', '')}",
                    f"- stage: {error.get('stage', '')}",
                    f"- details: {error.get('details', '')}",
                    f"- task_id: {error.get('task_id', '')}",
                ]
            )

    return "\n".join(lines) + "\n"
