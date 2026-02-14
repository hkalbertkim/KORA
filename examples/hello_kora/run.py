"""Run the hello_kora graph using the minimal deterministic executor."""

from __future__ import annotations

import json
from pathlib import Path

from kora.executor import run_graph
from kora.task_ir import TaskGraph, normalize_graph, validate_graph


def main() -> None:
    graph_path = Path(__file__).with_name("graph.json")
    graph = TaskGraph.from_json(graph_path)
    normalized = normalize_graph(graph)
    validate_graph(normalized)

    result = run_graph(normalized)
    print(json.dumps(result["final_output"], indent=2))


if __name__ == "__main__":
    main()
