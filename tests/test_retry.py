from kora.executor import run_graph
from kora.task_ir import TaskGraph, normalize_graph, validate_graph


def test_retry_demo_flaky_once_recovers_on_second_attempt() -> None:
    graph = TaskGraph.from_json("examples/retry_demo/graph.json")
    normalized = normalize_graph(graph)
    validate_graph(normalized)

    result = run_graph(normalized)

    assert result["final_output"]["status"] == "ok"

    task_events = [event for event in result["events"] if event["task_id"] == "task_flaky"]
    assert len(task_events) == 2
    assert task_events[0]["attempt"] == 1
    assert task_events[0]["status"] == "fail"
    assert task_events[1]["attempt"] == 2
    assert task_events[1]["status"] == "ok"
