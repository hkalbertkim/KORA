"""Task graph execution for v0.1-alpha."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Callable

from kora.adapters.base import BaseAdapter
from kora.adapters.mock import MockAdapter
from kora.adapters.openai_adapter import OpenAIAdapter, OpenAIFullAdapter, OpenAIMiniAdapter
from kora.errors import ErrorType, KoraRuntimeError, Stage
from kora.scheduler import get_task_map, topo_sort
from kora.task_ir import Task, TaskGraph
from kora.verification import verify_output

Handler = Callable[[Task, dict[str, Any]], dict[str, Any]]
ADAPTIVE_META_KEYS: tuple[str, ...] = (
    "confidence",
    "uncertainty",
    "voi",
    "escalate_recommended",
    "stop_reason",
)


class _AdapterRegistry:
    providers: dict[str, type[BaseAdapter]] = {
        "openai": OpenAIAdapter,
        "openai_mini": OpenAIMiniAdapter,
        "openai_full": OpenAIFullAdapter,
        "mock": MockAdapter,
    }

    @classmethod
    def get(cls, name: str) -> BaseAdapter:
        adapter_cls = cls.providers.get(name)
        if adapter_cls is None:
            raise ValueError(f"unknown llm adapter: {name}")
        return adapter_cls()


def _handle_echo(task: Task, state: dict[str, Any]) -> dict[str, Any]:
    del state
    message = task.in_.get("message")
    if message is None and task.run.kind == "det":
        message = task.run.spec.args.get("message")

    return {
        "status": "ok",
        "task_id": task.id,
        "message": message,
    }


def _handle_classify_simple(task: Task, state: dict[str, Any]) -> dict[str, Any]:
    del state
    text = task.in_.get("text")
    if text is None and task.run.kind == "det":
        text = task.run.spec.args.get("text", "")
    if not isinstance(text, str):
        text = str(text)

    return {
        "status": "ok",
        "task_id": task.id,
        "is_simple": len(text) < 80,
    }


def _handle_flaky_once(task: Task, state: dict[str, Any]) -> dict[str, Any]:
    attempts = state.setdefault("flaky_once_attempts", {})
    count = int(attempts.get(task.id, 0)) + 1
    attempts[task.id] = count

    if count == 1:
        raise ValueError("flaky_once: intentional fail")

    return {
        "status": "ok",
        "task_id": task.id,
        "message": "recovered",
    }


def _handle_parse_request_constraints(task: Task, state: dict[str, Any]) -> dict[str, Any]:
    del state
    text = task.in_.get("text")
    if text is None and task.run.kind == "det":
        text = task.run.spec.args.get("text", "")
    if not isinstance(text, str):
        text = str(text)
    lowered = text.lower()

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
        "status": "ok",
        "task_id": task.id,
        "intent": "create_presentation_outline",
        "deliverable_type": "ppt_outline",
        "slide_count": slide_count,
        "required_components": ["title", "key_message", "bullets", "presenter_notes"],
        "topic_domains": topic_domains[:6],
    }


def _handle_quality_gate(task: Task, state: dict[str, Any]) -> dict[str, Any]:
    if os.getenv("KORA_HIER_PLAN_ONLY", "") == "1":
        return {
            "status": "ok",
            "task_id": task.id,
            "message": "skip_full",
            "needs_refine": False,
            "reason": "plan_only",
        }

    if os.getenv("KORA_FORCE_FULL", "") == "1":
        return {
            "status": "ok",
            "task_id": task.id,
            "message": "run_full",
            "needs_refine": True,
            "reason": "forced_full",
        }

    outputs = state.get("outputs", {})
    if not isinstance(outputs, dict):
        outputs = {}

    dep_task_id = ""
    if task.run.kind == "det":
        dep_task_id = str(task.run.spec.args.get("dep_task_id", "")).strip()
    if not dep_task_id and task.deps:
        dep_task_id = task.deps[0]

    dep_output = outputs.get(dep_task_id, {})
    if not isinstance(dep_output, dict):
        dep_output = {}

    if not isinstance(dep_output.get("slides"), list):
        return {
            "status": "ok",
            "task_id": task.id,
            "message": "run_full",
            "needs_refine": True,
            "reason": "mini_missing_slides",
        }
    candidate: Any = dep_output

    target_slide_count = 18
    required_fields = ["i", "title", "msg", "bullets"]
    if task.run.kind == "det":
        target_slide_count = int(task.run.spec.args.get("target_slide_count", 18))
        custom_fields = task.run.spec.args.get("required_fields", required_fields)
        if isinstance(custom_fields, list) and custom_fields:
            required_fields = [str(f) for f in custom_fields]

    slides = candidate.get("slides")
    if not isinstance(slides, list) or len(slides) != target_slide_count:
        return {
            "status": "ok",
            "task_id": task.id,
            "message": "run_full",
            "needs_refine": True,
            "reason": "slide_count_mismatch",
        }

    for slide in slides:
        if not isinstance(slide, dict):
            return {
                "status": "ok",
                "task_id": task.id,
                "message": "run_full",
                "needs_refine": True,
                "reason": "slide_not_object",
            }
        if any(field not in slide for field in required_fields):
            return {
                "status": "ok",
                "task_id": task.id,
                "message": "run_full",
                "needs_refine": True,
                "reason": "slide_fields_missing",
            }
        if "bullets" in required_fields:
            bullets = slide.get("bullets")
            if not isinstance(bullets, list):
                return {
                    "status": "ok",
                    "task_id": task.id,
                    "message": "run_full",
                    "needs_refine": True,
                    "reason": "bullets_not_array",
                }
            if len(bullets) > 1:
                return {
                    "status": "ok",
                    "task_id": task.id,
                    "message": "run_full",
                    "needs_refine": True,
                    "reason": "bullets_too_many",
                }

    return {
        "status": "ok",
        "task_id": task.id,
        "message": "skip_full",
        "needs_refine": False,
        "reason": "mini_satisfies_contract",
    }


DETERMINISTIC_HANDLERS: dict[str, Handler] = {
    "echo": _handle_echo,
    "classify_simple": _handle_classify_simple,
    "flaky_once": _handle_flaky_once,
    "parse_request_constraints": _handle_parse_request_constraints,
    "quality_gate": _handle_quality_gate,
}


def normalize_answer_json_string(output: dict[str, Any]) -> dict[str, Any]:
    """Best-effort conversion of JSON-string answers into structured JSON."""
    answer = output.get("answer")
    if not isinstance(answer, str):
        return output

    trimmed = answer.lstrip()
    if not (trimmed.startswith("{") or trimmed.startswith("[")):
        return output

    try:
        parsed = json.loads(answer)
    except json.JSONDecodeError:
        return output

    if not isinstance(parsed, (dict, list)):
        return output

    normalized = dict(output)
    normalized["answer"] = parsed
    return normalized


def _run_det_task(task: Task, state: dict[str, Any]) -> dict[str, Any]:
    if task.run.kind != "det":
        raise ValueError(f"task '{task.id}' is not deterministic")

    handler_name = task.run.spec.handler
    handler = DETERMINISTIC_HANDLERS.get(handler_name)
    if handler is None:
        raise ValueError(f"unknown deterministic handler: {handler_name}")

    return handler(task, state)


def _skip_if_matches(task: Task, outputs: dict[str, dict[str, Any]]) -> bool:
    if task.run.kind != "llm":
        return False

    skip_if = task.run.spec.input.get("skip_if")
    if not isinstance(skip_if, dict):
        return False

    raw_path = str(skip_if.get("path", ""))
    expected = skip_if.get("equals")
    key = raw_path[2:] if raw_path.startswith("$.") else raw_path
    if not key:
        return False

    for dep_id in task.deps:
        dep_output = outputs.get(dep_id, {})
        if dep_output.get(key) == expected:
            return True

    return False


def _run_llm_task(
    task: Task,
    outputs: dict[str, dict[str, Any]],
    *,
    adapter_override: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if task.run.kind != "llm":
        raise ValueError(f"task '{task.id}' is not an llm task")

    adapter_name = adapter_override or task.run.spec.adapter
    adapter = _AdapterRegistry.get(adapter_name)
    adapter_input = dict(task.run.spec.input)
    adapter_input.pop("skip_if", None)

    budget = task.policy.budget.model_dump() if task.policy.budget is not None else {}
    result = adapter.run(
        task_id=task.id,
        input=adapter_input,
        budget=budget,
        output_schema=task.run.spec.output_schema,
    )
    meta = result.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    normalized_meta = dict(meta)
    for key in ADAPTIVE_META_KEYS:
        normalized_meta.setdefault(key, None)
    result["meta"] = normalized_meta

    if not result.get("ok"):
        raise ValueError(str(result.get("error", "adapter returned ok=false")))

    output = result.get("output")
    if not isinstance(output, dict):
        raise ValueError("adapter output must be a JSON object")

    output = normalize_answer_json_string(output)
    return output, result


def _resolve_escalation_adapter(base_adapter_name: str, stage_token: str) -> str | None:
    if stage_token in _AdapterRegistry.providers:
        return stage_token
    candidate = f"{base_adapter_name}:{stage_token}"
    if candidate in _AdapterRegistry.providers:
        return candidate
    return None


def _stage_token_from_adapter_name(adapter_name: str) -> str:
    if ":" in adapter_name:
        return adapter_name.rsplit(":", maxsplit=1)[1]
    return adapter_name


def _apply_adaptive_confidence_policy(
    task: Task,
    adapter_result: dict[str, Any],
    next_stage_token: str | None,
    stage_cost_estimates: dict[str, float],
) -> None:
    adaptive = task.policy.adaptive
    if adaptive is None:
        return

    meta = adapter_result.get("meta")
    if not isinstance(meta, dict):
        meta = {}
        adapter_result["meta"] = meta

    confidence_raw = meta.get("confidence")
    if isinstance(confidence_raw, bool) or not isinstance(confidence_raw, (int, float)):
        return

    confidence = max(0.0, min(1.0, float(confidence_raw)))
    uncertainty = 1.0 - confidence
    stage_cost = 1.0
    if next_stage_token is not None:
        if next_stage_token in adaptive.stage_costs:
            cost_raw = adaptive.stage_costs.get(next_stage_token, 1.0)
        else:
            cost_raw = stage_cost_estimates.get(next_stage_token, 1.0)
        if isinstance(cost_raw, (int, float)) and not isinstance(cost_raw, bool) and cost_raw > 0:
            stage_cost = float(cost_raw)
    meta["estimated_next_cost"] = stage_cost
    voi = uncertainty / stage_cost
    meta["uncertainty"] = uncertainty
    meta["voi"] = voi

    if confidence >= adaptive.min_confidence_to_stop:
        meta["escalate_recommended"] = False
        meta["stop_reason"] = "confident_enough"
        return

    if adaptive.use_voi and voi < adaptive.min_voi_to_escalate:
        meta["escalate_recommended"] = False
        meta["stop_reason"] = "voi_too_low"
        return

    meta["escalate_recommended"] = True
    meta["stop_reason"] = "escalate_confidence"


def run_graph(graph: TaskGraph) -> dict[str, Any]:
    """Execute a normalized task graph with structured success/failure contracts."""
    run_start = time.monotonic()
    outputs: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []
    state: dict[str, Any] = {}
    state["outputs"] = outputs
    stage_timings: dict[str, float] = {}
    state["stage_timings"] = stage_timings
    stage_cost_estimates: dict[str, float] = {}
    state["stage_cost_estimates"] = stage_cost_estimates
    order: list[str] = []

    scheduler_start = time.monotonic()
    try:
        order = topo_sort(graph)
        task_map = get_task_map(graph)
    except Exception as exc:
        scheduler_delta = time.monotonic() - scheduler_start
        stage_timings["scheduler_total_s"] = stage_timings.get("scheduler_total_s", 0.0) + scheduler_delta
        err = KoraRuntimeError(
            error_type=ErrorType.DAG_INVALID,
            stage=Stage.SCHEDULER,
            details=str(exc),
            retryable=False,
            budget_breached=False,
            cause=exc if isinstance(exc, Exception) else None,
        )
        result = {
            "ok": False,
            "graph_id": graph.graph_id,
            "order": order,
            "error": err.to_failure_contract(),
            "events": events,
            "outputs": outputs,
            "final": None,
        }
        result["stage_timings"] = stage_timings
        overall_delta = time.monotonic() - run_start
        stage_timings["overall_total_s"] = stage_timings.get("overall_total_s", 0.0) + overall_delta
        return result
    scheduler_delta = time.monotonic() - scheduler_start
    stage_timings["scheduler_total_s"] = stage_timings.get("scheduler_total_s", 0.0) + scheduler_delta

    for task_id in order:
        task = task_map[task_id]
        retries = task.policy.budget.max_retries if task.policy.budget is not None else 0
        max_attempts = 1 + max(0, retries)
        attempt = 0

        while True:
            attempt += 1
            start = time.monotonic()
            stage = Stage.UNKNOWN
            try:
                if task.run.kind == "det":
                    stage = Stage.DETERMINISTIC
                    det_start = time.monotonic()
                    output = _run_det_task(task, state)
                    det_delta = time.monotonic() - det_start
                    stage_timings["det_total_s"] = stage_timings.get("det_total_s", 0.0) + det_delta
                    det_verify_schema = task.verify.schema if task.verify is not None else None
                    if det_verify_schema:
                        stage = Stage.VERIFY
                        verify_start = time.monotonic()
                        verify_output(task, output)
                        verify_delta = time.monotonic() - verify_start
                        stage_timings["verify_total_s"] = stage_timings.get("verify_total_s", 0.0) + verify_delta
                    outputs[task.id] = output
                    events.append(
                        {
                            "task_id": task.id,
                            "attempt": attempt,
                            "status": "ok",
                            "stage": Stage.DETERMINISTIC.value,
                            "time_ms": int((time.monotonic() - start) * 1000),
                        }
                    )
                    break

                if task.run.kind == "llm":
                    stage = Stage.ADAPTER
                    if _skip_if_matches(task, outputs):
                        output = {
                            "status": "ok",
                            "task_id": task.id,
                            "skipped": True,
                            "message": "Skipped due to skip_if condition",
                        }
                        outputs[task.id] = output
                        events.append(
                            {
                                "task_id": task.id,
                                "attempt": attempt,
                                "status": "ok",
                                "stage": Stage.ADAPTER.value,
                                "time_ms": int((time.monotonic() - start) * 1000),
                                "skipped": True,
                            }
                        )
                        break

                    adaptive = task.policy.adaptive
                    escalation_order = list(adaptive.escalation_order) if adaptive is not None else []
                    escalation_step = 0
                    current_adapter = task.run.spec.adapter
                    base_adapter_name = task.run.spec.adapter
                    llm_events_for_attempt: list[dict[str, Any]] = []

                    while True:
                        next_stage_token = (
                            escalation_order[escalation_step]
                            if escalation_step < len(escalation_order)
                            else None
                        )
                        llm_start = time.monotonic()
                        output, adapter_result = _run_llm_task(
                            task,
                            outputs,
                            adapter_override=current_adapter,
                        )
                        llm_delta = time.monotonic() - llm_start
                        stage_timings["llm_total_s"] = stage_timings.get("llm_total_s", 0.0) + llm_delta
                        usage = adapter_result.get("usage")
                        cost_units: float | None = None
                        if isinstance(usage, dict):
                            tokens_in = usage.get("tokens_in")
                            tokens_out = usage.get("tokens_out")
                            if (
                                isinstance(tokens_in, (int, float))
                                and not isinstance(tokens_in, bool)
                                and isinstance(tokens_out, (int, float))
                                and not isinstance(tokens_out, bool)
                            ):
                                cost_units = float(tokens_in) + float(tokens_out)
                            else:
                                time_ms = usage.get("time_ms")
                                if isinstance(time_ms, (int, float)) and not isinstance(time_ms, bool):
                                    cost_units = float(time_ms)

                        meta = adapter_result.get("meta")
                        if not isinstance(meta, dict):
                            meta = {}
                            adapter_result["meta"] = meta
                        meta["cost_units"] = cost_units

                        if cost_units is not None:
                            stage_token_key = _stage_token_from_adapter_name(current_adapter)
                            old_est = stage_cost_estimates.get(stage_token_key, 1.0)
                            stage_cost_estimates[stage_token_key] = 0.3 * cost_units + (1.0 - 0.3) * old_est

                        _apply_adaptive_confidence_policy(
                            task,
                            adapter_result,
                            next_stage_token,
                            stage_cost_estimates,
                        )

                        llm_events_for_attempt.append(
                            {
                                "task_id": task.id,
                                "attempt": attempt,
                                "escalation_step": escalation_step,
                                "status": "ok",
                                "stage": Stage.ADAPTER.value,
                                "time_ms": int(llm_delta * 1000),
                                "usage": adapter_result.get("usage", {}),
                                "meta": adapter_result.get("meta", {}),
                            }
                        )

                        meta = adapter_result.get("meta", {})
                        should_escalate = bool(isinstance(meta, dict) and meta.get("escalate_recommended"))
                        if not should_escalate:
                            break

                        if adaptive is None:
                            break

                        if escalation_step >= adaptive.max_escalations:
                            if isinstance(meta, dict):
                                meta["stop_reason"] = "max_escalations"
                                meta["escalate_recommended"] = False
                            break

                        if escalation_step >= len(escalation_order):
                            if isinstance(meta, dict):
                                meta["stop_reason"] = "escalation_adapter_missing"
                                meta["escalate_recommended"] = False
                            break

                        stage_token = escalation_order[escalation_step]
                        next_adapter = _resolve_escalation_adapter(base_adapter_name, stage_token)
                        if next_adapter is None:
                            if isinstance(meta, dict):
                                meta["stop_reason"] = "escalation_adapter_missing"
                                meta["escalate_recommended"] = False
                            break

                        escalation_step += 1
                        current_adapter = next_adapter

                    stage = Stage.VERIFY
                    verify_start = time.monotonic()
                    verify_output(task, output)
                    verify_delta = time.monotonic() - verify_start
                    stage_timings["verify_total_s"] = stage_timings.get("verify_total_s", 0.0) + verify_delta
                    outputs[task.id] = output
                    events.extend(llm_events_for_attempt)
                    break

                raise KoraRuntimeError(
                    error_type=ErrorType.INVALID_TASK,
                    stage=Stage.IR,
                    details=f"run.kind '{task.run.kind}' not implemented in v0.1",
                    task_id=task.id,
                    retryable=False,
                    budget_breached=False,
                )

            except Exception as exc:
                if isinstance(exc, KoraRuntimeError):
                    runtime_error = exc
                else:
                    message = str(exc)
                    budget_breached = "budget" in message.lower()
                    if stage == Stage.VERIFY:
                        error_type = ErrorType.OUTPUT_SCHEMA_INVALID
                    elif stage == Stage.DETERMINISTIC:
                        error_type = ErrorType.DETERMINISTIC_EXEC_FAILED
                    elif stage == Stage.ADAPTER:
                        error_type = ErrorType.BUDGET_BREACH if budget_breached else ErrorType.ADAPTER_FAILED
                    else:
                        error_type = ErrorType.UNKNOWN

                    runtime_error = KoraRuntimeError(
                        error_type=error_type,
                        stage=stage,
                        details=message,
                        task_id=task.id,
                        retryable=(task.policy.on_fail == "retry" and attempt < max_attempts),
                        budget_breached=budget_breached,
                        cause=exc if isinstance(exc, Exception) else None,
                    )

                events.append(
                    {
                        "task_id": task.id,
                        "attempt": attempt,
                        "status": "fail",
                        "stage": runtime_error.stage.value,
                        "time_ms": int((time.monotonic() - start) * 1000),
                        "error": runtime_error.to_failure_contract(),
                    }
                )

                if task.policy.on_fail == "retry" and attempt < max_attempts:
                    continue

                if task.policy.on_fail == "escalate":
                    runtime_error = KoraRuntimeError(
                        error_type=ErrorType.ESCALATE_REQUIRED,
                        stage=runtime_error.stage,
                        details=runtime_error.details,
                        task_id=task.id,
                        retryable=False,
                        budget_breached=runtime_error.budget_breached,
                        cause=runtime_error,
                    )

                result = {
                    "ok": False,
                    "graph_id": graph.graph_id,
                    "order": order,
                    "error": runtime_error.to_failure_contract(),
                    "events": events,
                    "outputs": outputs,
                    "final": None,
                }
                result["stage_timings"] = stage_timings
                overall_delta = time.monotonic() - run_start
                stage_timings["overall_total_s"] = stage_timings.get("overall_total_s", 0.0) + overall_delta
                return result

    final_output = outputs.get(graph.root)
    result = {
        "ok": True,
        "graph_id": graph.graph_id,
        "order": order,
        "events": events,
        "outputs": outputs,
        "final": final_output,
    }
    result["stage_timings"] = stage_timings
    overall_delta = time.monotonic() - run_start
    stage_timings["overall_total_s"] = stage_timings.get("overall_total_s", 0.0) + overall_delta
    return result
