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


def _run_llm_task(task: Task, outputs: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    if task.run.kind != "llm":
        raise ValueError(f"task '{task.id}' is not an llm task")

    adapter = _AdapterRegistry.get(task.run.spec.adapter)
    adapter_input = dict(task.run.spec.input)
    adapter_input.pop("skip_if", None)

    budget = task.policy.budget.model_dump() if task.policy.budget is not None else {}
    result = adapter.run(
        task_id=task.id,
        input=adapter_input,
        budget=budget,
        output_schema=task.run.spec.output_schema,
    )

    if not result.get("ok"):
        raise ValueError(str(result.get("error", "adapter returned ok=false")))

    output = result.get("output")
    if not isinstance(output, dict):
        raise ValueError("adapter output must be a JSON object")

    output = normalize_answer_json_string(output)
    verify_output(task, output)
    return output, result


def run_graph(graph: TaskGraph) -> dict[str, Any]:
    """Execute a normalized task graph with structured success/failure contracts."""
    outputs: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []
    state: dict[str, Any] = {}
    state["outputs"] = outputs
    stage_timings: dict[str, float] = {}
    state["stage_timings"] = stage_timings
    order: list[str] = []

    try:
        order = topo_sort(graph)
        task_map = get_task_map(graph)
    except Exception as exc:
        err = KoraRuntimeError(
            error_type=ErrorType.DAG_INVALID,
            stage=Stage.SCHEDULER,
            details=str(exc),
            retryable=False,
            budget_breached=False,
            cause=exc if isinstance(exc, Exception) else None,
        )
        return {
            "ok": False,
            "graph_id": graph.graph_id,
            "order": order,
            "error": err.to_failure_contract(),
            "events": events,
            "outputs": outputs,
            "final": None,
        }

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
                    output = _run_det_task(task, state)
                    stage = Stage.VERIFY
                    verify_output(task, output)
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

                    output, adapter_result = _run_llm_task(task, outputs)
                    outputs[task.id] = output
                    events.append(
                        {
                            "task_id": task.id,
                            "attempt": attempt,
                            "status": "ok",
                            "stage": Stage.ADAPTER.value,
                            "time_ms": int((time.monotonic() - start) * 1000),
                            "usage": adapter_result.get("usage", {}),
                            "meta": adapter_result.get("meta", {}),
                        }
                    )
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

                return {
                    "ok": False,
                    "graph_id": graph.graph_id,
                    "order": order,
                    "error": runtime_error.to_failure_contract(),
                    "events": events,
                    "outputs": outputs,
                    "final": None,
                }

    final_output = outputs.get(graph.root)
    return {
        "ok": True,
        "graph_id": graph.graph_id,
        "order": order,
        "events": events,
        "outputs": outputs,
        "final": final_output,
    }
