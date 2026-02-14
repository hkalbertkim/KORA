from kora.executor import run_graph
from kora.task_ir import TaskGraph, normalize_graph, validate_graph


def test_run_graph_hello_kora() -> None:
    graph = TaskGraph.from_json("examples/hello_kora/graph.json")
    normalized = normalize_graph(graph)
    validate_graph(normalized)

    result = run_graph(normalized)
    final = result["final_output"]

    assert final["status"] == "ok"
    assert final["message"] == "hello from kora"
