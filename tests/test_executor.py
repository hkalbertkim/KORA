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
