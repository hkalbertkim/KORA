from kora.executor import run_graph
from kora.task_ir import TaskGraph, normalize_graph, validate_graph


def test_llm_skip_if_skips_adapter_call() -> None:
    graph = TaskGraph.model_validate(
        {
            "graph_id": "skip-demo",
            "version": "0.1",
            "root": "task_llm",
            "defaults": {
                "budget": {
                    "max_time_ms": 1500,
                    "max_tokens": 300,
                    "max_retries": 1,
                }
            },
            "tasks": [
                {
                    "id": "task_pre",
                    "type": "det.classify_simple",
                    "deps": [],
                    "in": {"text": "short"},
                    "run": {
                        "kind": "det",
                        "spec": {
                            "handler": "classify_simple",
                            "args": {"text": "short"},
                        },
                    },
                    "verify": {
                        "schema": {
                            "type": "object",
                            "required": ["status", "task_id", "is_simple"],
                        },
                        "rules": [
                            {
                                "kind": "required",
                                "paths": ["status", "task_id", "is_simple"],
                            }
                        ],
                    },
                    "policy": {"on_fail": "fail"},
                    "tags": [],
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
                                "question": "short",
                                "skip_if": {"path": "$.is_simple", "equals": True},
                            },
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
                        "budget": {
                            "max_time_ms": 1500,
                            "max_tokens": 300,
                            "max_retries": 1,
                        },
                        "on_fail": "retry",
                    },
                    "tags": [],
                },
            ],
        }
    )

    normalized = normalize_graph(graph)
    validate_graph(normalized)
    result = run_graph(normalized)

    assert result["outputs"]["task_llm"]["skipped"] is True
    llm_events = [e for e in result["events"] if e["task_id"] == "task_llm"]
    assert len(llm_events) == 1
    assert llm_events[0]["status"] == "ok"
    assert llm_events[0]["skipped"] is True
