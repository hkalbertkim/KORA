from kora.scheduler import topo_sort
from kora.task_ir import TaskGraph


def test_topo_sort_single_task_graph() -> None:
    graph = TaskGraph.from_json("examples/hello_kora/graph.json")
    assert topo_sort(graph) == ["task_echo"]


def test_topo_sort_three_task_dag() -> None:
    graph = TaskGraph.model_validate(
        {
            "graph_id": "dag-3",
            "version": "0.1",
            "root": "c",
            "defaults": {
                "budget": {
                    "max_time_ms": 1500,
                    "max_tokens": 300,
                    "max_retries": 1,
                }
            },
            "tasks": [
                {
                    "id": "a",
                    "type": "det.start",
                    "deps": [],
                    "in": {},
                    "run": {"kind": "det", "spec": {"handler": "noop", "args": {}}},
                    "verify": {"schema": {"type": "object"}, "rules": []},
                    "policy": {"on_fail": "fail"},
                    "tags": [],
                },
                {
                    "id": "b",
                    "type": "det.middle",
                    "deps": ["a"],
                    "in": {},
                    "run": {"kind": "det", "spec": {"handler": "noop", "args": {}}},
                    "verify": {"schema": {"type": "object"}, "rules": []},
                    "policy": {"on_fail": "fail"},
                    "tags": [],
                },
                {
                    "id": "c",
                    "type": "det.end",
                    "deps": ["a", "b"],
                    "in": {},
                    "run": {"kind": "det", "spec": {"handler": "noop", "args": {}}},
                    "verify": {"schema": {"type": "object"}, "rules": []},
                    "policy": {"on_fail": "fail"},
                    "tags": [],
                },
            ],
        }
    )

    assert topo_sort(graph) == ["a", "b", "c"]
