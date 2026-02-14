"""Task graph execution for v0.1-alpha."""

from __future__ import annotations

from typing import Any, Callable

from kora.scheduler import get_task_map, topo_sort
from kora.task_ir import Task, TaskGraph
from kora.verification import verify_output

Handler = Callable[[Task], dict[str, Any]]


def _handle_echo(task: Task) -> dict[str, Any]:
    message = task.in_.get("message")
    if message is None and task.run.kind == "det":
        message = task.run.spec.args.get("message")

    return {
        "status": "ok",
        "task_id": task.id,
        "message": message,
    }


DETERMINISTIC_HANDLERS: dict[str, Handler] = {
    "echo": _handle_echo,
}


def _run_det_task(task: Task) -> dict[str, Any]:
    if task.run.kind != "det":
        raise ValueError(f"task '{task.id}' is not deterministic")

    handler_name = task.run.spec.handler
    handler = DETERMINISTIC_HANDLERS.get(handler_name)
    if handler is None:
        raise ValueError(f"unknown deterministic handler: {handler_name}")

    return handler(task)


def run_graph(graph: TaskGraph) -> dict[str, Any]:
    """Execute a normalized task graph and return task/final outputs."""
    order = topo_sort(graph)
    task_map = get_task_map(graph)
    outputs: dict[str, dict[str, Any]] = {}

    for task_id in order:
        task = task_map[task_id]

        if task.run.kind != "det":
            raise NotImplementedError(f"run.kind '{task.run.kind}' not implemented in v0.1")

        retries = task.policy.budget.max_retries if task.policy.budget is not None else 0
        max_attempts = 1 + max(0, retries)
        attempt = 0

        while True:
            attempt += 1
            output = _run_det_task(task)
            try:
                verify_output(task, output)
                outputs[task.id] = output
                break
            except ValueError as exc:
                if task.policy.on_fail == "retry" and attempt < max_attempts:
                    continue
                if task.policy.on_fail == "escalate":
                    raise ValueError(
                        f"ESCALATE_REQUIRED: task '{task.id}' verification failed: {exc}"
                    ) from exc
                raise ValueError(
                    f"task '{task.id}' failed verification after {attempt} attempt(s): {exc}"
                ) from exc

    final_output = outputs[graph.root]
    return {
        "graph_id": graph.graph_id,
        "order": order,
        "outputs": outputs,
        "final_output": final_output,
    }
