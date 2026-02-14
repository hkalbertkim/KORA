from pathlib import Path

from kora.task_ir import TaskGraph, normalize_graph, validate_graph


def test_task_ir_load_normalize_validate_hello_graph() -> None:
    graph_path = Path("examples/hello_kora/graph.json")
    graph = TaskGraph.from_json(graph_path)

    normalized = normalize_graph(graph)
    validate_graph(normalized)

    task = normalized.tasks[0]
    assert normalized.version == "0.1"
    assert task.policy.budget is not None
    assert task.policy.budget.max_time_ms == 1500
