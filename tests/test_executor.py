from typing import Any

from kora.adapters.base import BaseAdapter
from kora.executor import run_graph
from kora.task_ir import TaskGraph, normalize_graph, validate_graph


def test_run_graph_hello_kora() -> None:
    graph = TaskGraph.from_json("examples/hello_kora/graph.json")
    normalized = normalize_graph(graph)
    validate_graph(normalized)

    result = run_graph(normalized)
    assert result["ok"] is True
    final = result["final"]

    assert final["status"] == "ok"
    assert final["message"] == "hello from kora"


def test_run_graph_det_without_schema_succeeds() -> None:
    graph = TaskGraph.model_validate(
        {
            "graph_id": "det-no-schema",
            "version": "0.1",
            "root": "task_echo",
            "defaults": {"budget": {"max_time_ms": 1500, "max_tokens": 300, "max_retries": 1}},
            "tasks": [
                {
                    "id": "task_echo",
                    "type": "det.echo",
                    "deps": [],
                    "in": {"message": "hello"},
                    "run": {"kind": "det", "spec": {"handler": "echo", "args": {}}},
                    "policy": {"on_fail": "fail"},
                    "tags": [],
                }
            ],
        }
    )
    normalized = normalize_graph(graph)
    validate_graph(normalized)
    result = run_graph(normalized)

    assert result["ok"] is True
    assert result["final"]["message"] == "hello"


def test_run_graph_det_with_schema_still_verifies() -> None:
    graph = TaskGraph.model_validate(
        {
            "graph_id": "det-with-schema",
            "version": "0.1",
            "root": "task_echo",
            "defaults": {"budget": {"max_time_ms": 1500, "max_tokens": 300, "max_retries": 1}},
            "tasks": [
                {
                    "id": "task_echo",
                    "type": "det.echo",
                    "deps": [],
                    "in": {"message": "hello"},
                    "run": {"kind": "det", "spec": {"handler": "echo", "args": {}}},
                    "verify": {"schema": {"type": "object", "required": ["must_exist"]}, "rules": []},
                    "policy": {"on_fail": "fail"},
                    "tags": [],
                }
            ],
        }
    )
    normalized = normalize_graph(graph)
    validate_graph(normalized)
    result = run_graph(normalized)

    assert result["ok"] is False
    assert result["error"]["error_type"] == "OUTPUT_SCHEMA_INVALID"


def test_adaptive_low_confidence_records_escalate_recommendation_without_escalation() -> None:
    from kora import executor as executor_module

    class LowConfidenceAdapter(BaseAdapter):
        call_count = 0

        def run(
            self,
            *,
            task_id: str,
            input: dict[str, Any],
            budget: dict[str, Any],
            output_schema: dict[str, Any],
        ) -> dict[str, Any]:
            del input, budget, output_schema
            LowConfidenceAdapter.call_count += 1
            return {
                "ok": True,
                "output": {
                    "status": "ok",
                    "task_id": task_id,
                    "answer": "low-confidence result",
                },
                "usage": {"time_ms": 1, "tokens_in": 1, "tokens_out": 1},
                "meta": {"adapter": "low_conf", "model": "mock-v0", "confidence": 0.1},
            }

    graph = TaskGraph.model_validate(
        {
            "graph_id": "adaptive-low-confidence",
            "version": "0.1",
            "root": "task_llm",
            "defaults": {"budget": {"max_time_ms": 1500, "max_tokens": 300, "max_retries": 1}},
            "tasks": [
                {
                    "id": "task_llm",
                    "type": "llm.answer",
                    "deps": [],
                    "in": {},
                    "run": {
                        "kind": "llm",
                        "spec": {
                            "adapter": "mock_low_conf",
                            "input": {"question": "q"},
                            "output_schema": {
                                "type": "object",
                                "required": ["status", "task_id", "answer"],
                            },
                        },
                    },
                    "verify": {
                        "schema": {
                            "type": "object",
                            "required": ["status", "task_id", "answer"],
                        },
                        "rules": [],
                    },
                    "policy": {
                        "on_fail": "fail",
                        "adaptive": {
                            "min_confidence_to_stop": 0.85,
                            "max_escalations": 2,
                            "escalation_order": ["mini", "gate", "full"],
                        },
                    },
                    "tags": [],
                }
            ],
        }
    )

    old_adapter = executor_module._AdapterRegistry.providers.get("mock_low_conf")
    executor_module._AdapterRegistry.providers["mock_low_conf"] = LowConfidenceAdapter
    LowConfidenceAdapter.call_count = 0
    try:
        normalized = normalize_graph(graph)
        validate_graph(normalized)
        result = run_graph(normalized)
    finally:
        if old_adapter is None:
            del executor_module._AdapterRegistry.providers["mock_low_conf"]
        else:
            executor_module._AdapterRegistry.providers["mock_low_conf"] = old_adapter

    assert result["ok"] is True
    llm_events = [event for event in result["events"] if event["task_id"] == "task_llm"]
    assert len(llm_events) == 1
    assert LowConfidenceAdapter.call_count == 1
    meta = llm_events[0]["meta"]
    assert meta["escalate_recommended"] is True
    assert meta["stop_reason"] == "escalate_confidence"
