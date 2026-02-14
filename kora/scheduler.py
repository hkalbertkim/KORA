"""DAG scheduling helpers for TaskGraph execution."""

from __future__ import annotations

from collections import deque
from typing import Any


def get_task_map(graph: Any) -> dict[str, Any]:
    """Build a task-id map from a graph-like object."""
    return {task.id: task for task in graph.tasks}


def detect_cycle(graph: Any) -> bool:
    """Return True when the task graph has a cycle."""
    task_map = get_task_map(graph)
    in_degree = {task_id: 0 for task_id in task_map}
    dependents: dict[str, list[str]] = {task_id: [] for task_id in task_map}

    for task in graph.tasks:
        for dep in task.deps:
            in_degree[task.id] += 1
            dependents[dep].append(task.id)

    queue = deque([task_id for task_id, degree in in_degree.items() if degree == 0])
    visited = 0

    while queue:
        current = queue.popleft()
        visited += 1
        for nxt in dependents[current]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    return visited != len(task_map)


def topo_sort(graph: Any) -> list[str]:
    """Topologically sort tasks by dependency order."""
    task_map = get_task_map(graph)
    in_degree = {task_id: 0 for task_id in task_map}
    dependents: dict[str, list[str]] = {task_id: [] for task_id in task_map}

    for task in graph.tasks:
        for dep in task.deps:
            if dep not in task_map:
                raise ValueError(f"task '{task.id}' depends on unknown task '{dep}'")
            in_degree[task.id] += 1
            dependents[dep].append(task.id)

    queue = deque(sorted(task_id for task_id, degree in in_degree.items() if degree == 0))
    order: list[str] = []

    while queue:
        current = queue.popleft()
        order.append(current)
        for nxt in sorted(dependents[current]):
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    if len(order) != len(task_map):
        raise ValueError("graph contains cycle; cannot compute topological order")

    return order
